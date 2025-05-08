from uuid import UUID

import pytest
import openai_responses
from openai import OpenAI
from sqlmodel import Session

from app.crud import CollectionCrud
from app.crud.rag import OpenAIAssistantCrud
from app.models import Collection
from app.tests.utils.document import DocumentStore
from app.tests.utils.collection import constants, get_collection


class TestCollectionDelete:
    _n_collections = 5

    @openai_responses.mock()
    def test_delete_marks_deleted(self, db: Session):
        client = OpenAI(api_key=constants.openai_mock_key)

        assistant = OpenAIAssistantCrud(client)
        collection = get_collection(db, client)

        crud = CollectionCrud(db, collection.owner_id)
        collection_ = crud.delete(collection, assistant)

        assert collection_.deleted_at is not None

    @openai_responses.mock()
    def test_delete_follows_insert(self, db: Session):
        client = OpenAI(api_key=constants.openai_mock_key)

        assistant = OpenAIAssistantCrud(client)
        collection = get_collection(db, client)

        crud = CollectionCrud(db, collection.owner_id)
        collection_ = crud.delete(collection, assistant)

        assert collection_.created_at <= collection_.deleted_at

    @openai_responses.mock()
    def test_cannot_delete_others_collections(self, db: Session):
        client = OpenAI(api_key=constants.openai_mock_key)

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

        client = OpenAI(api_key=constants.openai_mock_key)
        resources = []
        for _ in range(self._n_collections):
            coll = get_collection(db, client)
            crud = CollectionCrud(db, coll.owner_id)
            collection = crud.create(coll, documents)
            resources.append((crud, collection))

        ((crud, _), *_) = resources
        assistant = OpenAIAssistantCrud(client)
        crud.delete(documents[0], assistant)

        assert all(y.deleted_at for (_, y) in resources)
