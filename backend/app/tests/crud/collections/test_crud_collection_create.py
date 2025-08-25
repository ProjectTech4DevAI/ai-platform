import openai_responses
from sqlmodel import Session, select

from app.crud import CollectionCrud
from app.models import DocumentCollection
from app.tests.utils.document import DocumentStore
from app.tests.utils.collection import get_collection


class TestCollectionCreate:
    _n_documents = 10

    @openai_responses.mock()
    def test_create_associates_documents(self, db: Session):
        collection = get_collection(db)
        store = DocumentStore(db, project_id=collection.project_id)

        documents = store.fill(self._n_documents)
        crud = CollectionCrud(db, collection.owner_id)
        collection = crud.create(collection, documents)

        statement = select(DocumentCollection).where(
            DocumentCollection.collection_id == collection.id
        )

        source = set(x.id for x in documents)
        target = set(x.document_id for x in db.exec(statement))

        assert source == target
