import pytest
from openai_responses import OpenAIMock
from openai import OpenAI
from sqlmodel import Session

from app.crud import CollectionCrud, get_project_by_id
from app.models import Collection
from app.tests.utils.document import DocumentStore
from app.tests.utils.collection import get_collection


def create_collections(db: Session, n: int):
    crud = None

    openai_mock = OpenAIMock()
    with openai_mock.router:
        client = OpenAI(api_key="sk-test-key")
        for _ in range(n):
            collection = get_collection(db, client)
            project = get_project_by_id(session=db, project_id=collection.project_id)
            store = DocumentStore(db, project=project)
            documents = store.fill(1)
            if crud is None:
                crud = CollectionCrud(db, collection.owner_id)
            crud.create(collection, documents)

        return crud.owner_id


@pytest.fixture(scope="class")
def refresh(self, db: Session):
    db.query(Collection).delete()
    db.commit()


class TestCollectionReadAll:
    _ncollections = 5

    def test_number_read_is_expected(self, db: Session):
        db.query(Collection).delete()

        owner = create_collections(db, self._ncollections)
        crud = CollectionCrud(db, owner)
        docs = crud.read_all()

        assert len(docs) == self._ncollections

    def test_deleted_docs_are_excluded(self, db: Session):
        owner = create_collections(db, self._ncollections)
        crud = CollectionCrud(db, owner)
        assert all(x.deleted_at is None for x in crud.read_all())
