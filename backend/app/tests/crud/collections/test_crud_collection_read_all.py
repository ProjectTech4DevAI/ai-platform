import pytest
from openai_responses import OpenAIMock
from openai import OpenAI
from sqlmodel import Session

from app.crud import CollectionCrud
from app.core.config import settings
from app.models import Collection
from app.tests.utils.document import DocumentStore
from app.tests.utils.collection import get_collection
from app.tests.utils.utils import openai_credentials


def create_collections(db: Session, n: int):
    crud = None
    store = DocumentStore(db)
    documents = store.fill(1)

    openai_mock = OpenAIMock()
    with openai_mock.router:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        for _ in range(n):
            collection = get_collection(db, client)
            if crud is None:
                crud = CollectionCrud(db, collection.owner_id)
            crud.create(collection, documents)

        return crud.owner_id


@pytest.fixture(scope="class")
def refresh(self, db: Session):
    db.query(Collection).delete()
    db.commit()


@pytest.mark.usefixtures("openai_credentials")
class TestCollectionReadAll:
    _ncollections = 5

    def test_number_read_is_expected(
        self,
        db: Session,
    ):
        db.query(Collection).delete()

        owner = create_collections(db, self._ncollections)
        crud = CollectionCrud(db, owner)
        docs = crud.read_all()

        assert len(docs) == self._ncollections

    def test_deleted_docs_are_excluded(self, db: Session):
        owner = create_collections(db, self._ncollections)
        crud = CollectionCrud(db, owner)
        assert all(x.deleted_at is None for x in crud.read_all())
