import openai_responses
from openai import OpenAI
from sqlmodel import Session, select

from app.crud import CollectionCrud
from app.models import Collection, Document, DocumentCollection
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


class TestCollectionCreate:
    _api_key = "sk-fake"
    _n_documents = 10

    @openai_responses.mock()
    def test_create_associates_documents(self, db: Session):
        store = DocumentStore(db)
        documents = store.fill(self._n_documents)

        client = OpenAI(api_key=self._api_key)
        collection = get_collection(db, client)
        crud = CollectionCrud(db, collection.owner_id)
        collection = crud.create(collection, documents)

        statement = (
            select(Document, Collection)
            .join(
                DocumentCollection,
                DocumentCollection.document_id == Document.id,
            )
            .where(DocumentCollection.collection_id == collection.id)
        )

        docs = set(x.id for x in documents)
        for i in db.exec(statement):
            assert i.Document.id in docs and i.Collection.id == collection.id
