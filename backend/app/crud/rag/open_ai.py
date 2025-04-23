import json
import logging
import warnings
import functools as ft
from typing import Iterable

from openai import OpenAI, OpenAIError
from pydantic import BaseModel

from app.core.cloud import AmazonCloudStorage
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
                pass

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

    def update(self, vector_store_id: str, documents: Iterable[Document]):
        storage = AmazonCloudStorage()

        for docs in documents:
            view = {x.object_store_url: x for x in docs}
            req = self.client.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store_id,
                files=list(map(storage.stream, view)),
            )
            if req.file_counts.completed != req.file_counts.total:
                for i in self.read(vector_store_id):
                    if i.last_error is None:
                        object_store_url = self.client.files.retrieve(i.id)
                        view.pop(object_store_url)

                error = {
                    "error": "OpenAI document processing error",
                    "documents": view.values(),
                }
                raise InterruptedError(json.dumps(error, cls=BaseModelEncoder))

            yield from view.values()

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
        vector_store_ids = assistant.tool_resources.vector_stores
        try:
            (vector_store_id,) = vector_store_ids
        except ValueError as err:
            msg = "Too {} attached vectors: {}".format(
                "many" if vector_store_ids else "few",
                ", ".join(vector_store_ids),
            )
            raise ValueError(msg)

        v_crud = OpenAIVectorStoreCrud(self.client)
        v_crud.delete(vector_store_id)

        cleaner = AssistantCleaner(self.client)
        cleaner(vector_store_id)
