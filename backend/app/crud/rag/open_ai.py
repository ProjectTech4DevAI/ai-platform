import json
import logging
import warnings
import functools as ft
from typing import Iterable

from openai import OpenAI, OpenAIError
from pydantic import BaseModel

from app.core.cloud import CloudStorage
from app.core.config import settings
from app.models import Document

logger = logging.getLogger(__name__)


def vs_ls(client: OpenAI, vector_store_id: str):
    logger.info(
        f"[vs_ls] Listing files in vector store | {{'vector_store_id': '{vector_store_id}'}}"
    )
    kwargs = {}
    while True:
        page = client.vector_stores.files.list(
            vector_store_id=vector_store_id,
            **kwargs,
        )
        logger.info(
            f"[vs_ls] Retrieved page of files | {{'vector_store_id': '{vector_store_id}', 'has_more': {page.has_more}}}"
        )
        yield from page
        if not page.has_more:
            break
        kwargs["after"] = page.last_id


class BaseModelEncoder(json.JSONEncoder):
    @ft.singledispatchmethod
    def default(self, o):
        return super().default(o)

    @default.register
    def _(self, o: BaseModel):
        logger.info(
            f"[BaseModelEncoder.default] Encoding BaseModel object | {{'model_type': '{type(o).__name__}'}}"
        )
        return o.model_dump()


class ResourceCleaner:
    def __init__(self, client):
        self.client = client
        logger.info(
            f"[ResourceCleaner.init] Initialized cleaner | {{'cleaner_type': '{type(self).__name__}'}}"
        )

    def __str__(self):
        return type(self).__name__

    def __call__(self, resource, retries=1):
        logger.info(
            f"[ResourceCleaner.call] Starting resource cleanup | {{'cleaner_type': '{self}', 'resource': '{resource}', 'retries': {retries}}}"
        )
        for i in range(retries):
            try:
                self.clean(resource)
                logger.info(
                    f"[ResourceCleaner.call] Resource cleaned successfully | {{'cleaner_type': '{self}', 'resource': '{resource}'}}"
                )
                return
            except OpenAIError as err:
                logger.error(
                    f"[ResourceCleaner.call] OpenAI error during cleanup | {{'cleaner_type': '{self}', 'resource': '{resource}', 'error': '{str(err)}'}}"
                )

        logger.warning(
            f"[ResourceCleaner.call] Cleanup failure after retries | {{'cleaner_type': '{self}', 'resource': '{resource}'}}"
        )
        warnings.warn(f"[{self} {resource}] Cleanup failure")

    def clean(self, resource):
        raise NotImplementedError()


class AssistantCleaner(ResourceCleaner):
    def clean(self, resource):
        logger.info(
            f"[AssistantCleaner.clean] Deleting assistant | {{'assistant_id': '{resource}'}}"
        )
        self.client.beta.assistants.delete(resource)


class VectorStoreCleaner(ResourceCleaner):
    def clean(self, resource):
        logger.info(
            f"[VectorStoreCleaner.clean] Starting vector store cleanup | {{'vector_store_id': '{resource}'}}"
        )
        for i in vs_ls(self.client, resource):
            logger.info(
                f"[VectorStoreCleaner.clean] Deleting file | {{'vector_store_id': '{resource}', 'file_id': '{i.id}'}}"
            )
            self.client.files.delete(i.id)
        logger.info(
            f"[VectorStoreCleaner.clean] Deleting vector store | {{'vector_store_id': '{resource}'}}"
        )
        self.client.vector_stores.delete(resource)


class OpenAICrud:
    def __init__(self, client=None):
        self.client = client or OpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info(
            f"[OpenAICrud.init] Initialized OpenAI CRUD | {{'has_client': {client is not None}}}"
        )


class OpenAIVectorStoreCrud(OpenAICrud):
    def create(self):
        logger.info(
            f"[OpenAIVectorStoreCrud.create] Creating vector store | {{'action': 'create'}}"
        )
        vector_store = self.client.vector_stores.create()
        logger.info(
            f"[OpenAIVectorStoreCrud.create] Vector store created | {{'vector_store_id': '{vector_store.id}'}}"
        )
        return vector_store

    def read(self, vector_store_id: str):
        logger.info(
            f"[OpenAIVectorStoreCrud.read] Reading files from vector store | {{'vector_store_id': '{vector_store_id}'}}"
        )
        yield from vs_ls(self.client, vector_store_id)

    def update(
        self,
        vector_store_id: str,
        storage: CloudStorage,
        documents: Iterable[Document],
    ):
        logger.info(
            f"[OpenAIVectorStoreCrud.update] Starting vector store update | {{'vector_store_id': '{vector_store_id}'}}"
        )
        files = []
        for docs in documents:
            for d in docs:
                logger.info(
                    f"[OpenAIVectorStoreCrud.update] Streaming document | {{'vector_store_id': '{vector_store_id}', 'document_id': '{d.id}', 'filename': '{d.fname}'}}"
                )
                f_obj = storage.stream(d.object_store_url)

                # monkey patch botocore.response.StreamingBody to make
                # OpenAI happy
                f_obj.name = d.fname

                files.append(f_obj)

            logger.info(
                f"[OpenAIVectorStoreCrud.update] Uploading files to vector store | {{'vector_store_id': '{vector_store_id}', 'file_count': {len(files)}}}"
            )
            req = self.client.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store_id,
                files=files,
            )
            logger.info(
                f"[OpenAIVectorStoreCrud.update] File upload completed | {{'vector_store_id': '{vector_store_id}', 'completed_files': {req.file_counts.completed}, 'total_files': {req.file_counts.total}}}"
            )
            if req.file_counts.completed != req.file_counts.total:
                view = {x.fname: x for x in docs}
                for i in self.read(vector_store_id):
                    if i.last_error is None:
                        fname = self.client.files.retrieve(i.id)
                        view.pop(fname)

                error = {
                    "error": "OpenAI document processing error",
                    "documents": list(view.values()),
                }
                logger.error(
                    f"[OpenAIVectorStoreCrud.update] Document processing error | {{'vector_store_id': '{vector_store_id}', 'error': '{error['error']}', 'failed_documents': {len(error['documents'])}}}"
                )
                raise InterruptedError(json.dumps(error, cls=BaseModelEncoder))

            while files:
                f_obj = files.pop()
                f_obj.close()
                logger.info(
                    f"[OpenAIVectorStoreCrud.update] Closed file stream | {{'vector_store_id': '{vector_store_id}', 'filename': '{f_obj.name}'}}"
                )

            yield from docs

    def delete(self, vector_store_id: str, retries: int = 3):
        logger.info(
            f"[OpenAIVectorStoreCrud.delete] Starting vector store deletion | {{'vector_store_id': '{vector_store_id}', 'retries': {retries}}}"
        )
        if retries < 1:
            logger.error(
                f"[OpenAIVectorStoreCrud.delete] Invalid retries value | {{'vector_store_id': '{vector_store_id}', 'retries': {retries}}}"
            )
            raise ValueError("Retries must be greater-than 1")

        cleaner = VectorStoreCleaner(self.client)
        cleaner(vector_store_id)
        logger.info(
            f"[OpenAIVectorStoreCrud.delete] Vector store deleted | {{'vector_store_id': '{vector_store_id}'}}"
        )


class OpenAIAssistantCrud(OpenAICrud):
    def create(self, vector_store_id: str, **kwargs):
        logger.info(
            f"[OpenAIAssistantCrud.create] Creating assistant | {{'vector_store_id': '{vector_store_id}'}}"
        )
        assistant = self.client.beta.assistants.create(
            tools=[
                {
                    "type": "file_search",
                }
            ],
            tool_resources={
                "file_search": {
                    "vector_store_ids": [
                        vector_store_id,
                    ],
                },
            },
            **kwargs,
        )
        logger.info(
            f"[OpenAIAssistantCrud.create] Assistant created | {{'assistant_id': '{assistant.id}', 'vector_store_id': '{vector_store_id}'}}"
        )
        return assistant

    def delete(self, assistant_id: str):
        logger.info(
            f"[OpenAIAssistantCrud.delete] Starting assistant deletion | {{'assistant_id': '{assistant_id}'}}"
        )
        assistant = self.client.beta.assistants.retrieve(assistant_id)
        vector_stores = assistant.tool_resources.file_search.vector_store_ids
        try:
            (vector_store_id,) = vector_stores
        except ValueError as err:
            if vector_stores:
                names = ", ".join(vector_stores)
                logger.error(
                    f"[OpenAIAssistantCrud.delete] Too many vector stores attached | {{'assistant_id': '{assistant_id}', 'vector_stores': '{names}'}}"
                )
                raise ValueError(f"Too many attached vector stores: {names}")
            else:
                logger.error(
                    f"[OpenAIAssistantCrud.delete] No vector stores found | {{'assistant_id': '{assistant_id}'}}"
                )
                raise ValueError("No vector stores found")

        logger.info(
            f"[OpenAIAssistantCrud.delete] Deleting vector store | {{'assistant_id': '{assistant_id}', 'vector_store_id': '{vector_store_id}'}}"
        )
        v_crud = OpenAIVectorStoreCrud(self.client)
        v_crud.delete(vector_store_id)

        logger.info(
            f"[OpenAIAssistantCrud.delete] Deleting assistant | {{'assistant_id': '{assistant_id}'}}"
        )
        cleaner = AssistantCleaner(self.client)
        cleaner(assistant_id)
        logger.info(
            f"[OpenAIAssistantCrud.delete] Assistant deleted | {{'assistant_id': '{assistant_id}'}}"
        )