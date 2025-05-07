from uuid import UUID

import pytest
import openai_responses
from openai import OpenAI
from sqlmodel import Session

from app.crud import CollectionCrud
from app.crud.rag import OpenAIAssistantCrud
from app.models import Collection
from app.tests.utils.utils import get_user_id_by_email
from app.tests.utils.document import DocumentStore


def get_collection(db, client):
    owner_id = get_user_id_by_email(db)

    vector_store = client.vector_stores.create()
    assistant = client.beta.assistants.create(
        model="gpt-4o",
        tools=[
            {
                "type": "file_search",
            },
        ],
        tool_resources={
            "file_search": {
                "vector_store_ids": [
                    vector_store.id,
                ],
            },
        },
    )

    return Collection(
        owner_id=owner_id,
        llm_service_id=assistant.id,
        llm_service_name="test-service-name",
    )


class TestCollectionDelete:
    _api_key = "sk-fake123"
    _n_collections = 5

    @openai_responses.mock()
    def test_delete_marks_deleted(self, db: Session):
        client = OpenAI(api_key=self._api_key)

        assistant = OpenAIAssistantCrud(client)
        collection = get_collection(db, client)

        crud = CollectionCrud(db, collection.owner_id)
        collection_ = crud.delete(collection, assistant)

        assert collection_.deleted_at is not None

    @openai_responses.mock()
    def test_delete_follows_insert(self, db: Session):
        client = OpenAI(api_key=self._api_key)

        assistant = OpenAIAssistantCrud(client)
        collection = get_collection(db, client)

        crud = CollectionCrud(db, collection.owner_id)
        collection_ = crud.delete(collection, assistant)

        assert collection_.created_at <= collection_.deleted_at

    @openai_responses.mock()
    def test_cannot_delete_others_collections(self, db: Session):
        client = OpenAI(api_key=self._api_key)

        assistant = OpenAIAssistantCrud(client)
        collection = get_collection(db, client)

        value = int(collection.id) + 1  # hopefully doesn't overflow
        c_id = UUID(int=value)

        crud = CollectionCrud(db, c_id)
        with pytest.raises(PermissionError):
            crud.delete(collection, assistant)

    @openai_responses.mock()
    def test_delete_document_deletes_collections(self, db: Session):
        store = DocumentStore(db)
        documents = store.fill(1)

        client = OpenAI(api_key=self._api_key)
        resources = []
        for _ in range(self._n_collections):
            coll = get_collection(db, client)
            crud = CollectionCrud(db, coll.owner_id)
            collection = crud.create(coll, documents)
            resources.append((crud, collection))

        ((crud, _), *_) = resources
        assistant = OpenAIAssistantCrud(client)
        crud.delete(documents[0], assistant)

        for _, c in resources:
            assert c.deleted_at is not None
