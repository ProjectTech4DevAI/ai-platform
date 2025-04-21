import json
import logging
import warnings
import functools as ft
from typing import Iterable

from openai import OpenAIError
from pydantic import BaseModel

from app.core.cloud import AmazonCloudStorage
from app.models import Document


class BaseModelEncoder(json.JSONEncoder):
    @ft.singledispatchmethod
    def default(self, o):
        return super().default(o)

    @default.register
    def _(self, o: BaseModel):
        return o.model_dump()


class OpenAICrud:
    def __init__(self, client):
        self.client = client


class OpenAIVectorStoreCrud(OpenAICrud):
    def create(self):
        return self.client.beta.vector_stores.create()

    def read(self, vector_store_id: str):
        kwargs = {}
        while True:
            page = self.client.beta.vector_stores.files.list(
                vector_store_id=vector_store_id,
                **kwargs,
            )
            yield from page
            if not page.has_more:
                break
            kwargs["after"] = page.last_id

    def update(self, vector_store_id: str, documents: Iterable[Document]):
        storage = AmazonCloudStorage()

        for docs in documents:
            view = {x.object_store_url: x for x in docs}
            batch = self.client.beta.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store_id,
                files=list(map(storage.stream, view)),
            )
            if batch.file_counts.completed != batch.file_counts.total:
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

        for i in range(retries):
            try:
                for i in self.read(vector_store_id):
                    self.client.files.delete(i.id)
                self.client.beta.vector_stores.delete(vector_store_id)

                return
            except OpenAIError as err:
                logging.error(
                    "[{} of {}] {} vector store purge error: {}".format(
                        i + 1,
                        retries,
                        vector_store_id,
                        err,
                    )
                )

        warnings.warn(f"Unable to purge vector store resources ({vector_store_id})")


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
