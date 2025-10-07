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
    CollectionActionType,
)
from app.models.collection import (
    ResponsePayload,
    CreationRequest,
    AssistantOptions,
)
from app.services.collections.helpers import (
    _backout,
    batch_documents,
    SilentCallback,
    WebHookCallback,
)
from app.celery.utils import start_low_priority_job
from app.utils import get_openai_client

logger = logging.getLogger(__name__)


def start_job(
    db: Session,
    request: dict,
    project_id: int,
    payload: dict,
    collection_job_id: str,
    organization_id: int,
) -> str:
    trace_id = correlation_id.get() or "N/A"

    collection_job = CollectionJob(
        id=UUID(collection_job_id),
        action_type=CollectionActionType.CREATE,
        project_id=project_id,
        status=CollectionJobStatus.PENDING,
    )

    job_crud = CollectionJobCrud(db, project_id)
    collection_job = job_crud.create(collection_job)

    task_id = start_low_priority_job(
        function_path="app.services.collections.create_collection.execute_job",
        project_id=project_id,
        job_id=collection_job_id,
        trace_id=trace_id,
        request=request,
        payload_data=payload,
        organization_id=organization_id,
    )

    logger.info(
        "[create_collection.start_job] Job scheduled to create collection | "
        f"collection_job_id={collection_job_id}, project_id={project_id}, task_id={task_id}"
    )

    return collection_job_id


def execute_job(
    request: dict,
    payload_data: dict,
    project_id: int,
    organization_id: int,
    task_id: str,
    job_id: str,
    task_instance,
) -> None:
    """
    Worker entrypoint scheduled by start_job.
    """
    start_time = time.time()

    try:
        with Session(engine) as session:
            creation_request = CreationRequest(**request)
            payload = ResponsePayload(**payload_data)

            job_id = UUID(job_id)

            collection_job_crud = CollectionJobCrud(session, project_id)
            collection_job = collection_job_crud.read_one(job_id)
            collection_job.task_id = task_id
            collection_job.status = CollectionJobStatus.PROCESSING
            collection_job_crud.update(collection_job.id, collection_job)

            client = get_openai_client(session, organization_id, project_id)

            callback = (
                SilentCallback(payload)
                if creation_request.callback_url is None
                else WebHookCallback(creation_request.callback_url, payload)
            )

            storage = get_cloud_storage(session=session, project_id=project_id)
            document_crud = DocumentCrud(session, project_id)
            assistant_crud = OpenAIAssistantCrud(client)
            vector_store_crud = OpenAIVectorStoreCrud(client)

            try:
                vector_store = vector_store_crud.create()

                docs_batches = batch_documents(
                    document_crud,
                    creation_request.documents,
                    creation_request.batch_size,
                )
                flat_docs = [doc for batch in docs_batches for doc in batch]

                file_exts = {
                    doc.fname.split(".")[-1] for doc in flat_docs if "." in doc.fname
                }
                file_sizes_kb = [
                    storage.get_file_size_kb(doc.object_store_url) for doc in flat_docs
                ]

                list(vector_store_crud.update(vector_store.id, storage, docs_batches))

                assistant_options = dict(
                    creation_request.extract_super_type(AssistantOptions)
                )
                assistant = assistant_crud.create(vector_store.id, **assistant_options)

                collection_id = uuid4()
                collection_crud = CollectionCrud(session, project_id)
                collection = Collection(
                    id=collection_id,
                    project_id=project_id,
                    organization_id=organization_id,
                    llm_service_id=assistant.id,
                    llm_service_name=creation_request.model,
                )

                collection_crud.create(collection)
                collection_data = collection_crud.read_one(collection.id)

                if flat_docs:
                    DocumentCollectionCrud(session).create(collection_data, flat_docs)

                collection_crud.create(collection_data)

                collection_job.status = CollectionJobStatus.SUCCESSFUL
                collection_job.collection_id = collection_id
                collection_job_crud.update(collection_job.id, collection_job)

                elapsed = time.time() - start_time
                logger.info(
                    "[create_collection.execute_job] Collection created: %s | Time: %.2fs | Files: %d | Sizes: %s KB | Types: %s",
                    collection_id,
                    elapsed,
                    len(flat_docs),
                    file_sizes_kb,
                    list(file_exts),
                )

                callback.success(collection.model_dump(mode="json"))

            except Exception as err:
                logger.error(
                    "[create_collection.execute_job] Collection Creation Failed | "
                    "{'collection_job_id': '%s', 'error': '%s'}",
                    job_id,
                    str(err),
                    exc_info=True,
                )

                if "assistant" in locals():
                    _backout(assistant_crud, assistant.id)

                collection_job.status = CollectionJobStatus.FAILED
                collection_job.error_message = str(err)
                collection_job_crud.update(collection_job.id, collection_job)

                callback.fail(str(err))

    except Exception as outer_err:
        logger.error(
            "[create_collection.execute_job] Unexpected Error during collection creation: %s",
            str(outer_err),
            exc_info=True,
        )

        collection_job.status = CollectionJobStatus.FAILED
        collection_job.error_message = str(err)
        collection_job_crud.update(collection_job.id, collection_job)
