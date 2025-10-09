import logging
from uuid import UUID

from sqlmodel import Session
from asgi_correlation_id import correlation_id
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import engine
from app.crud import CollectionCrud, CollectionJobCrud
from app.crud.rag import OpenAIAssistantCrud
from app.models import CollectionJobStatus, CollectionJobUpdate
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
    request: DeletionRequest,
    collection: Collection,
    project_id: int,
    collection_job_id: UUID,
    payload: ResponsePayload,
    organization_id: int,
) -> str:
    trace_id = correlation_id.get() or "N/A"

    job_crud = CollectionJobCrud(db, project_id)
    collection_job = job_crud.update(
        collection_job_id, CollectionJobUpdate(trace_id=trace_id)
    )

    task_id = start_low_priority_job(
        function_path="app.services.collections.delete_collection.execute_job",
        project_id=project_id,
        job_id=str(collection_job_id),
        collection_id=str(collection.id),
        trace_id=trace_id,
        request=request.model_dump(),
        payload=payload.model_dump(),
        organization_id=organization_id,
    )

    logger.info(
        "[delete_collection.start_job] Job scheduled to delete collection | "
        f"Job_id={collection_job_id}, project_id={project_id}, task_id={task_id}, collection_id={collection.id}"
    )
    return collection_job_id


def execute_job(
    request: dict,
    payload: dict,
    project_id: int,
    organization_id: int,
    task_id: str,
    job_id: str,
    collection_id: str,
    task_instance,
) -> None:
    deletion_request = DeletionRequest(**request)
    payload = ResponsePayload(**payload)

    callback = (
        SilentCallback(payload)
        if deletion_request.callback_url is None
        else WebHookCallback(deletion_request.callback_url, payload)
    )

    collection_id = UUID(collection_id)
    job_id = UUID(job_id)

    try:
        with Session(engine) as session:
            client = get_openai_client(session, organization_id, project_id)

            collection_job_crud = CollectionJobCrud(session, project_id)
            collection_job = collection_job_crud.read_one(job_id)
            collection_job = collection_job_crud.update(
                job_id,
                CollectionJobUpdate(
                    task_id=task_id, status=CollectionJobStatus.PROCESSING
                ),
            )

            assistant_crud = OpenAIAssistantCrud(client)
            collection_crud = CollectionCrud(session, project_id)

            collection = collection_crud.read_one(collection_id)

            try:
                result = collection_crud.delete(collection, assistant_crud)

                collection_job.status = CollectionJobStatus.SUCCESSFUL
                collection_job.error_message = None
                collection_job_crud.update(collection_job.id, collection_job)

                logger.info(
                    "[delete_collection.execute_job] Collection deleted successfully | {'collection_id': '%s', 'job_id': '%s'}",
                    str(collection.id),
                    str(job_id),
                )
                callback.success(result.model_dump(mode="json"))

            except (ValueError, PermissionError, SQLAlchemyError) as err:
                collection_job.status = CollectionJobStatus.FAILED
                collection_job.error_message = str(err)
                collection_job_crud.update(collection_job.id, collection_job)

                logger.error(
                    "[delete_collection.execute_job] Failed to delete collection | {'collection_id': '%s', 'error': '%s', 'job_id': '%s'}",
                    str(collection.id),
                    str(err),
                    str(job_id),
                    exc_info=True,
                )
                callback.fail(str(err))

    except Exception as err:
        collection_job.status = CollectionJobStatus.FAILED
        collection_job.error_message = str(err)
        collection_job_crud.update(collection_job.id, collection_job)

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
