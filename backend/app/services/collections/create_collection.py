import logging
import time
from uuid import UUID

from sqlmodel import Session
from asgi_correlation_id import correlation_id

from app.core.cloud import get_cloud_storage
from app.core.util import now
from app.core.db import engine
from app.crud import (
    DocumentCrud,
    CollectionCrud,
    DocumentCollectionCrud,
)
from app.crud.rag import OpenAIVectorStoreCrud, OpenAIAssistantCrud
from app.models import Collection
from app.models.collection import (
    CollectionStatus,
    ResponsePayload,
    CreationRequest,
    AssistantOptions,
)
from app.services.collections.helpers import _backout, SilentCallback, WebHookCallback
from app.celery.utils import start_low_priority_job
from app.utils import get_openai_client

logger = logging.getLogger(__name__)


def start_job(
    db: Session,  # kept for signature compatibility, even if unused here
    request: dict,
    collection: Collection,
    project_id: int,
    payload: dict,
    organization_id: int,
) -> UUID:
    trace_id = correlation_id.get() or "N/A"

    task_id = start_low_priority_job(
        # keep the function path in sync with the worker entrypoint below
        function_path="app.services.collections.create_collection.execute_job",
        project_id=project_id,
        job_id=collection.id,
        trace_id=trace_id,
        request=request,
        payload_data=payload,
        organization_id=organization_id,
    )

    logger.info(
        "[start_job] Job scheduled to create collection | "
        f"collection_id={collection.id}, project_id={project_id}, task_id={task_id}, job_id={collection.id}"
    )
    return collection.id


def execute_job(
    request: dict,
    payload_data: dict,
    project_id: int,
    organization_id: int,
    task_id: str,
    job_id: UUID,
    task_instance,
) -> None:
    """
    Worker entrypoint scheduled by start_job.
    """
    start_time = time.time()

    with Session(engine) as session:
        # Parse/validate incoming data
        creation_request = CreationRequest(**request)
        payload = ResponsePayload(**payload_data)

        collection_crud = CollectionCrud(session, project_id)
        collection = collection_crud.read_one(job_id)
        collection.task_id = task_id
        collection_crud._update(collection)

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

            docs_batches = list(creation_request(document_crud))
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

            collection = collection_crud.read_one(collection.id)  # refresh
            collection.llm_service_id = assistant.id
            collection.llm_service_name = creation_request.model
            collection.status = CollectionStatus.successful
            collection.updated_at = now()

            if flat_docs:
                DocumentCollectionCrud(session).create(collection, flat_docs)

            collection_crud._update(collection)

            elapsed = time.time() - start_time
            logger.info(
                "[do_create_collection] Collection created: %s | Time: %.2fs | Files: %d | Sizes: %s KB | Types: %s",
                collection.id,
                elapsed,
                len(flat_docs),
                file_sizes_kb,
                list(file_exts),
            )

            callback.success(collection.model_dump(mode="json"))

        except Exception as err:
            logger.error(
                "[do_create_collection] Collection Creation Failed | {'collection_id': '%s', 'error': '%s'}",
                collection.id,
                str(err),
                exc_info=True,
            )

            if "assistant" in locals():
                _backout(assistant_crud, assistant.id)

            try:
                collection = collection_crud.read_one(job_id)
                collection.status = CollectionStatus.failed
                collection.updated_at = now()
                collection.error_message = str(err)
                collection_crud._update(collection)
            except Exception as suberr:
                logger.warning(
                    "[do_create_collection] Failed to update collection status | "
                    "{'collection_id': '%s', 'reason': '%s'}",
                    collection.id,
                    str(suberr),
                )

            callback.fail(str(err))
