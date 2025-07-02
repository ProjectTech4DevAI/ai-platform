import pytest
from sqlmodel import Session

from app.crud import DocumentCrud

from app.tests.utils.document import DocumentMaker, DocumentStore
from app.seed_data.seed_data import seed_database


@pytest.fixture(scope="function", autouse=True)
def load_seed_data(db):
    """Load seed data before each test."""
    seed_database(db)
    yield


@pytest.fixture
def documents(db: Session, api_key_headers: dict[str, str]):
    store = DocumentStore(db, api_key_headers)
    return store.documents


class TestDatabaseUpdate:
    def test_update_adds_one(self, db: Session, documents: DocumentMaker):
        crud = DocumentCrud(db, documents.owner_id)

        before = crud.read_many()
        crud.update(next(documents))
        after = crud.read_many()

        assert len(before) + 1 == len(after)

    def test_sequential_update_is_ordered(
        self,
        db: Session,
        documents: DocumentMaker,
    ):
        crud = DocumentCrud(db, documents.owner_id)
        (a, b) = (crud.update(y) for (_, y) in zip(range(2), documents))

        assert a.inserted_at <= b.inserted_at

    def test_insert_does_not_delete(
        self,
        db: Session,
        documents: DocumentMaker,
    ):
        crud = DocumentCrud(db, documents.owner_id)
        document = crud.update(next(documents))

        assert document.deleted_at is None

    def test_update_sets_default_owner(
        self,
        db: Session,
        documents: DocumentMaker,
    ):
        crud = DocumentCrud(db, documents.owner_id)
        document = next(documents)
        document.owner_id = None
        result = crud.update(document)

        assert result.owner_id == document.owner_id

    def test_update_respects_owner(
        self,
        db: Session,
        documents: DocumentMaker,
    ):
        document = next(documents)
        document.owner_id = documents.index.peek()

        crud = DocumentCrud(db, documents.owner_id)
        with pytest.raises(PermissionError):
            crud.update(document)
