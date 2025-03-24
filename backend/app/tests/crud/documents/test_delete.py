import pytest
from sqlmodel import Session, select

from app.crud import DocumentCrud
from app.models import Document

from _utils import (
    insert_document,
    rm_documents,
)

@pytest.fixture
def document(db: Session):
    rm_documents(db)
    document = insert_document(db)

    crud = DocumentCrud(db)
    crud.delete(document.id, document.owner_id)

    statement = (
        select(Document)
        .where(Document.id == document.id)
    )
    return db.exec(statement).one()

class TestDatabaseUpdate:
    def test_delete_is_soft(self, document: Document):
        assert document is not None

    def test_delete_marks_deleted(self, document: Document):
        assert document.deleted_at is not None

    def test_delete_follows_insert(self, document: Document):
        assert document.created_at <= document.deleted_at
