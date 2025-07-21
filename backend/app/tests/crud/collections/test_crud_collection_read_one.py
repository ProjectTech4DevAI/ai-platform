import pytest
from openai import OpenAI
from openai_responses import OpenAIMock
from sqlmodel import Session
from sqlalchemy.exc import NoResultFound

from app.core.config import settings
from app.crud import CollectionCrud
from app.tests.utils.document import DocumentStore
from app.tests.utils.collection import get_collection, uuid_increment
from app.tests.utils.utils import openai_credentials
from app.seed_data.seed_data import seed_database


@pytest.fixture(scope="function", autouse=True)
def load_seed_data(db):
    """Load seed data before each test."""
    seed_database(db)
    yield


def mk_collection(db: Session):
    store = DocumentStore(db)
    documents = store.fill(1)

    openai_mock = OpenAIMock()
    with openai_mock.router:
        client = OpenAI(api_key="Test_api_key")
        collection = get_collection(db, client)
        crud = CollectionCrud(db, collection.owner_id)
        return crud.create(collection, documents)


@pytest.mark.usefixtures("openai_credentials")
class TestDatabaseReadOne:
    def test_can_select_valid_id(self, db: Session):
        collection = mk_collection(db)

        crud = CollectionCrud(db, collection.owner_id)
        result = crud.read_one(collection.id)

        assert result.id == collection.id

    def test_cannot_select_others_collections(self, db: Session):
        collection = mk_collection(db)

        other = collection.owner_id + 1
        crud = CollectionCrud(db, other)
        with pytest.raises(NoResultFound):
            crud.read_one(collection.id)
