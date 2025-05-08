import openai_responses
from sqlmodel import Session, select

from app.crud import CollectionCrud
from app.models import Collection, Document, DocumentCollection
from app.tests.utils.document import DocumentStore
from app.tests.utils.collection import get_collection


class TestCollectionCreate:
    _n_documents = 10

    @openai_responses.mock()
    def test_create_associates_documents(self, db: Session):
        store = DocumentStore(db)
        documents = store.fill(self._n_documents)

        collection = get_collection(db)
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
