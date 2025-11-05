import logging
import time
from uuid import UUID, uuid4

from sqlmodel import Session
from asgi_correlation_id import correlation_id

from app.core.cloud import get_cloud_storage
from app.core.util import now
from app.core.db import engine
from app.crud import (
    CollectionCrud,
    DocumentCrud,
    DocumentCollectionCrud,
    CollectionJobCrud,
)
from app.crud.rag import OpenAIVectorStoreCrud, OpenAIAssistantCrud
from app.models import (
    CollectionJobStatus,
    CollectionJob,
    Collection,
    CollectionJobUpdate,
    CollectionPublic,
    CollectionJobPublic,
)
from app.models.collection import (
    CreationRequest,
    AssistantOptions,
)
from app.services.collections.helpers import (
    _backout,
    batch_documents,
    extract_error_message,
    OPENAI_VECTOR_STORE,
)
from app.celery.utils import start_low_priority_job
from app.utils import get_openai_client, send_callback, APIResponse


logger = logging.getLogger(__name__)


def start_job(
    db: Session,
    request: CreationRequest,
    project_id: int,
    collection_job_id: UUID,
    with_assistant: bool,
    organization_id: int,
) -> str:
    trace_id = correlation_id.get() or "N/A"

    job_crud = CollectionJobCrud(db, project_id)
    collection_job = job_crud.update(
        collection_job_id, CollectionJobUpdate(trace_id=trace_id)
    )

    task_id = start_low_priority_job(
        function_path="app.services.collections.create_collection.execute_job",
        project_id=project_id,
        job_id=str(collection_job_id),
        trace_id=trace_id,
        with_assistant=with_assistant,
        request=request.model_dump(mode="json"),
        organization_id=organization_id,
    )

    logger.info(
        "[create_collection.start_job] Job scheduled to create collection | "
        f"collection_job_id={collection_job_id}, project_id={project_id}, task_id={task_id}"
    )

    return collection_job_id


def build_success_payload(
    collection_job: CollectionJob, collection: Collection
) -> dict:
    """
    {
      "success": true,
      "data": { job fields + full collection },
      "error": null,
      "metadata": null
    }
    """
    collection_public = CollectionPublic.model_validate(collection)
    job_public = CollectionJobPublic.model_validate(
        collection_job,
        update={"collection": collection_public},
    )
    return APIResponse.success_response(job_public).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )


def build_failure_payload(collection_job: CollectionJob, error_message: str) -> dict:
    """
    {
      "success": false,
      "data": { job fields, collection: null },
      "error": "something went wrong",
      "metadata": null
    }
    """
    # ensure `collection` is explicitly null in the payload
    job_public = CollectionJobPublic.model_validate(
        collection_job,
        update={"collection": None},
    )
    return APIResponse.failure_response(
        extract_error_message(error_message), job_public
    ).model_dump(
        mode="json",
        by_alias=True,
        exclude={"data": {"error_message"}},
    )


def _cleanup_remote_resources(
    assistant,
    assistant_crud,
    vector_store,
    vector_store_crud,
) -> None:
    """Best-effort cleanup of partially created remote resources."""
    try:
        if assistant is not None and assistant_crud is not None:
            _backout(assistant_crud, assistant.id)
        elif vector_store is not None and vector_store_crud is not None:
            _backout(vector_store_crud, vector_store.id)
        else:
            logger.warning(
                "[create_collection._backout] Skipping: no resource/crud available"
            )
    except Exception:
        logger.warning("[create_collection.execute_job] Backout failed")


def _mark_job_failed(
    project_id: int,
    job_id: str,
    err: Exception,
    collection_job: CollectionJob | None,
) -> CollectionJob | None:
    """Update job row to FAILED with error_message; return latest job or None."""
    try:
        with Session(engine) as session:
            collection_job_crud = CollectionJobCrud(session, project_id)
            if collection_job is None:
                collection_job = collection_job_crud.read_one(UUID(job_id))
            collection_job = collection_job_crud.update(
                collection_job.id,
                CollectionJobUpdate(
                    status=CollectionJobStatus.FAILED,
                    error_message=str(err),
                ),
            )
            return collection_job
    except Exception:
        logger.warning("[create_collection.execute_job] Failed to mark job as FAILED")
        return None


def execute_job(
    request: dict,
    project_id: int,
    organization_id: int,
    task_id: str,
    job_id: str,
    with_assistant: bool,
    task_instance,
) -> None:
    """
    Worker entrypoint scheduled by start_job.
    Orchestrates: job state, client/storage init, batching, vector-store upload,
    optional assistant creation, collection persistence, linking, callbacks, and cleanup.
    """
    start_time = time.time()

    # Keep references for potential backout/cleanup on failure
    assistant = None
    assistant_crud = None
    vector_store = None
    vector_store_crud = None
    collection_job = None
    callback = None

    try:
        creation_request = CreationRequest(**request)
        job_uuid = UUID(job_id)

        with Session(engine) as session:
            collection_job_crud = CollectionJobCrud(session, project_id)
            collection_job = collection_job_crud.read_one(job_uuid)
            collection_job = collection_job_crud.update(
                job_uuid,
                CollectionJobUpdate(
                    task_id=task_id,
                    status=CollectionJobStatus.PROCESSING,
                ),
            )

            client = get_openai_client(session, organization_id, project_id)
            storage = get_cloud_storage(session=session, project_id=project_id)

            # Batch documents for upload, and flatten for linking/metrics later
            document_crud = DocumentCrud(session, project_id)
            docs_batches = batch_documents(
                document_crud,
                creation_request.documents,
                creation_request.batch_size,
            )
            flat_docs = [doc for batch in docs_batches for doc in batch]

        vector_store_crud = OpenAIVectorStoreCrud(client)
        vector_store = vector_store_crud.create()
        list(vector_store_crud.update(vector_store.id, storage, docs_batches))

        #  if with_assistant is true, create assistant backed by the vector store
        if with_assistant:
            assistant_crud = OpenAIAssistantCrud(client)

            # Filter out None to avoid sending unset options
            assistant_options = dict(
                creation_request.extract_super_type(AssistantOptions)
            )
            assistant_options = {
                k: v for k, v in assistant_options.items() if v is not None
            }

            assistant = assistant_crud.create(vector_store.id, **assistant_options)
            llm_service_id = assistant.id
            llm_service_name = assistant_options.get("model") or "assistant"

            logger.info(
                "[execute_job] Assistant created | assistant_id=%s, vector_store_id=%s",
                assistant.id,
                vector_store.id,
            )
        else:
            # If no assistant, the collection points directly at the vector store
            llm_service_id = vector_store.id
            llm_service_name = OPENAI_VECTOR_STORE
            logger.info(
                "[execute_job] Skipping assistant creation | with_assistant=False"
            )

        file_exts = {doc.fname.split(".")[-1] for doc in flat_docs if "." in doc.fname}
        file_sizes_kb = [
            storage.get_file_size_kb(doc.object_store_url) for doc in flat_docs
        ]

        with Session(engine) as session:
            collection_crud = CollectionCrud(session, project_id)

            collection_id = uuid4()
            collection = Collection(
                id=collection_id,
                project_id=project_id,
                organization_id=organization_id,
                llm_service_id=llm_service_id,
                llm_service_name=llm_service_name,
            )
            collection_crud.create(collection)
            collection = collection_crud.read_one(collection.id)

            # Link documents to the new collection
            if flat_docs:
                DocumentCollectionCrud(session).create(collection, flat_docs)

            collection_job_crud = CollectionJobCrud(session, project_id)
            collection_job = collection_job_crud.update(
                collection_job.id,
                CollectionJobUpdate(
                    status=CollectionJobStatus.SUCCESSFUL,
                    collection_id=collection.id,
                ),
            )

            success_payload = build_success_payload(collection_job, collection)

        elapsed = time.time() - start_time
        logger.info(
            "[create_collection.execute_job] Collection created: %s | Time: %.2fs | Files: %d | Sizes: %s KB | Types: %s",
            collection_id,
            elapsed,
            len(flat_docs),
            file_sizes_kb,
            list(file_exts),
        )

        if creation_request.callback_url:
            send_callback(creation_request.callback_url, success_payload)

    except Exception as err:
        logger.error(
            "[create_collection.execute_job] Collection Creation Failed | {'collection_job_id': '%s', 'error': '%s'}",
            job_id,
            str(err),
            exc_info=True,
        )

        _cleanup_remote_resources(
            assistant=assistant,
            assistant_crud=assistant_crud,
            vector_store=vector_store,
            vector_store_crud=vector_store_crud,
        )

        collection_job = _mark_job_failed(
            project_id=project_id,
            job_id=job_id,
            err=err,
            collection_job=collection_job,
        )

        if creation_request and creation_request.callback_url and collection_job:
            failure_payload = build_failure_payload(collection_job, str(err))
            send_callback(creation_request.callback_url, failure_payload)
