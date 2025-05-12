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


def vs_ls(client: OpenAI, vector_store_id: str):
    kwargs = {}
    while True:
        page = client.vector_stores.files.list(
            vector_store_id=vector_store_id,
            **kwargs,
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
        return o.model_dump()


class ResourceCleaner:
    def __init__(self, client):
        self.client = client

    def __str__(self):
        return type(self).__name__

    def __call__(self, resource, retries=1):
        for i in range(retries):
            try:
                self.clean(resource)
                return
            except OpenAIError as err:
                logging.error(err)

        warnings.warn(f"[{self} {resource}] Cleanup failure")

    def clean(self, resource):
        raise NotImplementedError()


class AssistantCleaner(ResourceCleaner):
    def clean(self, resource):
        self.client.beta.assistants.delete(resource)


class VectorStoreCleaner(ResourceCleaner):
    def clean(self, resource):
        for i in vs_ls(self.client, resource):
            self.client.files.delete(i.id)
        self.client.vector_stores.delete(resource)


class OpenAICrud:
    def __init__(self, client=None):
        self.client = client or OpenAI(api_key=settings.OPENAI_API_KEY)


class OpenAIVectorStoreCrud(OpenAICrud):
    def create(self):
        return self.client.vector_stores.create()

    def read(self, vector_store_id: str):
        yield from vs_ls(self.client, vector_store_id)

    def update(
        self,
        vector_store_id: str,
        storage: CloudStorage,
        documents: Iterable[Document],
    ):
        files = []
        for docs in documents:
            for d in docs:
                f_obj = storage.stream(d.object_store_url)

                # monkey patch botocore.response.StreamingBody to make
                # OpenAI happy
                f_obj.name = d.fname

                files.append(f_obj)

            req = self.client.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store_id,
                files=files,
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
                raise InterruptedError(json.dumps(error, cls=BaseModelEncoder))

            while files:
                f_obj = files.pop()
                f_obj.close()

            yield from docs

    def delete(self, vector_store_id: str, retries: int = 3):
        if retries < 1:
            raise ValueError("Retries must be greater-than 1")

        cleaner = VectorStoreCleaner(self.client)
        cleaner(vector_store_id)


class OpenAIAssistantCrud(OpenAICrud):
    def create(self, vector_store_id: str, **kwargs):
        return self.client.beta.assistants.create(
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

    def delete(self, assistant_id: str):
        assistant = self.client.beta.assistants.retrieve(assistant_id)
        vector_stores = assistant.tool_resources.file_search.vector_store_ids
        try:
            (vector_store_id,) = vector_stores
        except ValueError as err:
            if vector_stores:
                names = ", ".join(vector_stores)
                msg = f"Too many attached vector stores: {names}"
            else:
                msg = "No vector stores found"
            raise ValueError(msg)

        v_crud = OpenAIVectorStoreCrud(self.client)
        v_crud.delete(vector_store_id)

        cleaner = AssistantCleaner(self.client)
        cleaner(assistant_id)
