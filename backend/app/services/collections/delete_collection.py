import logging
from uuid import UUID, uuid4

from sqlmodel import Session
from asgi_correlation_id import correlation_id
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import engine
from app.crud import CollectionCrud, CollectionJobCrud
from app.crud.rag import OpenAIAssistantCrud
from app.models import CollectionJob, CollectionJobStatus
from app.models.collection import Collection, DeletionRequest
from app.services.collections.helpers import (
    SilentCallback,
    WebHookCallback,
    ResponsePayload,
)
from app.celery.utils import start_low_priority_job
from app.utils import get_openai_client


logger = logging.getLogger(__name__)


def start_job(
    db: Session,
    request: dict,
    collection: Collection,
    project_id: int,
    payload: dict,
    organization_id: int,
) -> UUID:
    trace_id = correlation_id.get() or "N/A"

    job_id = uuid4()

    collection_job = CollectionJob(
        id=job_id,
        action_type="delete",
        project_id=project_id,
        collection_id=collection.id,
        status=CollectionJobStatus.processing,
    )

    job_crud = CollectionJobCrud(db, project_id)
    collection_job = job_crud.create(collection_job)

    task_id = start_low_priority_job(
        function_path="app.services.collections.delete_collection.execute_job",
        project_id=project_id,
        job_id=job_id,
        collection_id=collection.id,
        trace_id=trace_id,
        request=request,
        payload_data=payload,
        organization_id=organization_id,
    )

    logger.info(
        "[delete_collection.start_job] Job scheduled to delete collection | "
        f"Job_id={job_id}, project_id={project_id}, task_id={task_id}, collection_id={collection.id}"
    )
    return collection.id


def execute_job(
    request: dict,
    payload_data: dict,
    project_id: int,
    organization_id: int,
    task_id: str,
    job_id: UUID,
    collection_id: UUID,
    task_instance,
) -> None:
    deletion_request = DeletionRequest(**request)
    payload = ResponsePayload(**payload_data)

    callback = (
        SilentCallback(payload)
        if deletion_request.callback_url is None
        else WebHookCallback(deletion_request.callback_url, payload)
    )

    try:
        with Session(engine) as session:
            client = get_openai_client(session, organization_id, project_id)
            assistant_crud = OpenAIAssistantCrud(client)
            collection_crud = CollectionCrud(session, project_id)
            collection_job_crud = CollectionJobCrud(session, project_id)

            collection = collection_crud.read_one(collection_id)
            collection_job = collection_job_crud.read_one(job_id)

            collection_job.task_id = task_id

            try:
                result = collection_crud.delete(collection, assistant_crud)

                collection_job.status = CollectionJobStatus.successful
                collection_job.error_message = None
                collection_job_crud._update(collection_job)

                logger.info(
                    "[delete_collection.execute_job] Collection deleted successfully | {'collection_id': '%s', 'job_id': '%s'}",
                    str(collection.id),
                    str(job_id),
                )
                callback.success(result.model_dump(mode="json"))

            except (ValueError, PermissionError, SQLAlchemyError) as err:
                collection_job.status = CollectionJobStatus.failed
                collection_job.error_message = str(err)
                collection_job_crud._update(collection_job)

                logger.error(
                    "[delete_collection.execute_job] Failed to delete collection | {'collection_id': '%s', 'error': '%s', 'job_id': '%s'}",
                    str(collection.id),
                    str(err),
                    str(job_id),
                    exc_info=True,
                )
                callback.fail(str(err))

    except Exception as err:
        collection_job.status = CollectionJobStatus.failed
        collection_job.error_message = str(err)
        collection_job_crud._update(collection_job)

        logger.error(
            "[delete_collection.execute_job] Unexpected error during deletion | "
            "{'collection_id': '%s', 'error': '%s', 'error_type': '%s', 'job_id': '%s'}",
            str(collection.id),
            str(err),
            type(err).__name__,
            str(job_id),
            exc_info=True,
        )
        callback.fail(str(err))
