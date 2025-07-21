import pytest
from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound

from app.crud import DocumentCrud
from app.models import Document

from app.tests.utils.document import DocumentStore
from app.core.exception_handlers import HTTPException
from app.seed_data.seed_data import seed_database


@pytest.fixture(scope="function", autouse=True)
def load_seed_data(db):
    """Load seed data before each test."""
    seed_database(db)
    yield


@pytest.fixture
def document(db: Session):
    store = DocumentStore(db)
    document = store.put()

    crud = DocumentCrud(db, document.owner_id)
    crud.delete(document.id)

    statement = select(Document).where(Document.id == document.id)
    return db.exec(statement).one()


class TestDatabaseDelete:
    def test_delete_is_soft(self, document: Document):
        assert document is not None

    def test_delete_marks_deleted(self, document: Document):
        assert document.deleted_at is not None

    def test_delete_follows_insert(self, document: Document):
        assert document.inserted_at <= document.deleted_at

    def test_cannot_delete_others_documents(self, db: Session):
        store = DocumentStore(db)
        document = store.put()
        other_owner_id = store.documents.owner_id + 1

        crud = DocumentCrud(db, other_owner_id)
        with pytest.raises(HTTPException) as exc_info:
            crud.delete(document.id)

        assert exc_info.value.status_code == 404
        assert "Document not found" in str(exc_info.value.detail)
