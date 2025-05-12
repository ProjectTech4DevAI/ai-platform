import pytest
import openai_responses
from openai import OpenAI
from sqlmodel import Session

from app.core.config import settings
from app.crud import CollectionCrud
from app.crud.rag import OpenAIAssistantCrud
from app.tests.utils.document import DocumentStore
from app.tests.utils.collection import (
    get_collection,
    openai_credentials,
    uuid_increment,
)


@pytest.mark.usefixtures("openai_credentials")
class TestCollectionDelete:
    _n_collections = 5

    @openai_responses.mock()
    def test_delete_marks_deleted(self, db: Session):
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        assistant = OpenAIAssistantCrud(client)
        collection = get_collection(db, client)

        crud = CollectionCrud(db, collection.owner_id)
        collection_ = crud.delete(collection, assistant)

        assert collection_.deleted_at is not None

    @openai_responses.mock()
    def test_delete_follows_insert(self, db: Session):
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        assistant = OpenAIAssistantCrud(client)
        collection = get_collection(db, client)

        crud = CollectionCrud(db, collection.owner_id)
        collection_ = crud.delete(collection, assistant)

        assert collection_.created_at <= collection_.deleted_at

    @openai_responses.mock()
    def test_cannot_delete_others_collections(self, db: Session):
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        assistant = OpenAIAssistantCrud(client)
        collection = get_collection(db, client)
        c_id = uuid_increment(collection.id)

        crud = CollectionCrud(db, c_id)
        with pytest.raises(PermissionError):
            crud.delete(collection, assistant)

    @openai_responses.mock()
    def test_delete_document_deletes_collections(self, db: Session):
        store = DocumentStore(db)
        documents = store.fill(1)

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
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
