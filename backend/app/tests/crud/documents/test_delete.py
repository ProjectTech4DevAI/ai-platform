import pytest
from sqlmodel import Session, select

from app.crud import DocumentCrud
from app.models import Document

from app.tests.utils.document import DocumentStore

@pytest.fixture
def document(db: Session):
    store = DocumentStore(db)
    document = store.put()

    crud = DocumentCrud(db)
    crud.delete(document.id, document.owner_id)

    statement = (
        select(Document)
        .where(Document.id == document.id)
    )
    return db.exec(statement).one()

class TestDatabaseDelete:
    def test_delete_is_soft(self, document: Document):
        assert document is not None

    def test_delete_marks_deleted(self, document: Document):
        assert document.deleted_at is not None

    def test_delete_follows_insert(self, document: Document):
        assert document.created_at <= document.deleted_at
