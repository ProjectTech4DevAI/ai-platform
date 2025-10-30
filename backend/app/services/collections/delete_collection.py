import logging
from uuid import UUID

from sqlmodel import Session
from asgi_correlation_id import correlation_id

from app.core.db import engine
from app.crud import CollectionCrud, CollectionJobCrud
from app.crud.rag import OpenAIAssistantCrud, OpenAIVectorStoreCrud
from app.models import CollectionJobStatus, CollectionJobUpdate
from app.models.collection import DeletionRequest
from app.services.collections.helpers import (
    SilentCallback,
    WebHookCallback,
    OPENAI_VECTOR_STORE,
)
from app.celery.utils import start_low_priority_job
from app.utils import get_openai_client


logger = logging.getLogger(__name__)


def start_job(
    db: Session,
    request: DeletionRequest,
    project_id: int,
    collection_job_id: UUID,
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
        collection_id=str(request.collection_id),
        trace_id=trace_id,
        request=request.model_dump(mode="json"),
        organization_id=organization_id,
    )

    logger.info(
        "[delete_collection.start_job] Job scheduled to delete collection | "
        f"Job_id={collection_job_id}, project_id={project_id}, task_id={task_id}, collection_id={request.collection_id}"
    )
    return collection_job_id


def execute_job(
    request: dict,
    project_id: int,
    organization_id: int,
    task_id: str,
    job_id: str,
    collection_id: str,
    task_instance,
) -> None:
    """Celery worker entrypoint for deleting a collection (both remote and local)."""

    deletion_request = DeletionRequest(**request)

    collection_id = UUID(collection_id)
    job_id = UUID(job_id)

    collection_job = None
    client = None

    with Session(engine) as session:
        client = get_openai_client(session, organization_id, project_id)

        collection_job_crud = CollectionJobCrud(session, project_id)
        collection_job = collection_job_crud.read_one(job_id)
        collection_job = collection_job_crud.update(
            job_id,
            CollectionJobUpdate(task_id=task_id, status=CollectionJobStatus.PROCESSING),
        )

        # Load the collection record
        collection = CollectionCrud(session, project_id).read_one(collection_id)

        # Identify which external service (assistant/vector store) this collection belongs to
        service = (collection.llm_service_name or "").strip().lower()
        is_vector = service == OPENAI_VECTOR_STORE

        llm_service_id = (
            (
                getattr(collection, "vector_store_id", None)
                or getattr(collection, "llm_service_id", None)
            )
            if is_vector
            else (
                getattr(collection, "assistant_id", None)
                or getattr(collection, "llm_service_id", None)
            )
        )

        callback = (
            SilentCallback(collection_job)
            if not deletion_request.callback_url
            else WebHookCallback(deletion_request.callback_url, collection_job)
        )

    #  EXTERNAL SERVICE DELETION
    try:
        # Validate that we have a valid external service ID
        if not llm_service_id:
            raise ValueError(
                f"Missing llm service id for service '{collection.llm_service_name}' on collection {collection_id}"
            )

        # Delete the corresponding OpenAI resource (vector store or assistant)
        if is_vector:
            OpenAIVectorStoreCrud(client).delete(llm_service_id)
        else:
            OpenAIAssistantCrud(client).delete(llm_service_id)

    except Exception as err:
        try:
            with Session(engine) as session:
                collection_job_crud = CollectionJobCrud(session, project_id)
                collection_job_crud.update(
                    collection_job.id,
                    CollectionJobUpdate(
                        status=CollectionJobStatus.FAILED, error_message=str(err)
                    ),
                )
                collection_job = collection_job_crud.read_one(collection_job.id)
        except Exception:
            logger.warning(
                "[delete_collection.execute_job] Failed to mark job as FAILED"
            )

        logger.error(
            "[delete_collection.execute_job] Failed to delete collection remotely | "
            "{'collection_id': '%s', 'error': '%s', 'job_id': '%s'}",
            str(collection_id),
            str(err),
            str(job_id),
            exc_info=True,
        )

        # Notify via callback if configured
        if callback:
            callback.collection_job = collection_job
            callback.fail(str(err))
        return

    #  LOCAL DELETION
    try:
        with Session(engine) as session:
            CollectionCrud(session, project_id).delete_by_id(collection_id)

            collection_job_crud = CollectionJobCrud(session, project_id)
            collection_job_crud.update(
                collection_job.id,
                CollectionJobUpdate(
                    status=CollectionJobStatus.SUCCESSFUL, error_message=None
                ),
            )
            collection_job = collection_job_crud.read_one(collection_job.id)

        logger.info(
            "[delete_collection.execute_job] Collection deleted successfully | {'collection_id': '%s', 'job_id': '%s'}",
            str(collection_id),
            str(job_id),
        )

        if callback:
            callback.collection_job = collection_job
            callback.success({"collection_id": str(collection_id), "deleted": True})

    except Exception as err:
        # Handle any failure during local DB deletion
        try:
            with Session(engine) as session:
                collection_job_crud = CollectionJobCrud(session, project_id)
                collection_job_crud.update(
                    collection_job.id,
                    CollectionJobUpdate(
                        status=CollectionJobStatus.FAILED, error_message=str(err)
                    ),
                )
                collection_job = collection_job_crud.read_one(collection_job.id)
        except Exception:
            logger.warning(
                "[delete_collection.execute_job] Failed to mark job as FAILED"
            )

        logger.error(
            "[delete_collection.execute_job] Unexpected error during local deletion | "
            "{'collection_id': '%s', 'error': '%s', 'error_type': '%s', 'job_id': '%s'}",
            str(collection_id),
            str(err),
            type(err).__name__,
            str(job_id),
            exc_info=True,
        )

        if callback:
            callback.collection_job = collection_job
            callback.fail(str(err))
