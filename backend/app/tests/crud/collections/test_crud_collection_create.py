import pytest
import openai_responses
from sqlmodel import Session, select

from app.crud import CollectionCrud
from app.models import DocumentCollection
from app.tests.utils.document import DocumentStore
from app.tests.utils.collection import get_collection
from app.tests.utils.utils import openai_credentials
from app.seed_data.seed_data import seed_database


@pytest.fixture(scope="function", autouse=True)
def load_seed_data(db):
    """Load seed data before each test."""
    seed_database(db)
    yield


@pytest.mark.usefixtures("openai_credentials")
class TestCollectionCreate:
    _n_documents = 10

    @openai_responses.mock()
    def test_create_associates_documents(
        self, db: Session, api_key_headers: dict[str, str]
    ):
        store = DocumentStore(db, api_key_headers)
        documents = store.fill(self._n_documents)

        collection = get_collection(db)
        crud = CollectionCrud(db, collection.owner_id)
        collection = crud.create(collection, documents)

        statement = select(DocumentCollection).where(
            DocumentCollection.collection_id == collection.id
        )

        source = set(x.id for x in documents)
        target = set(x.document_id for x in db.exec(statement))

        assert source == target
