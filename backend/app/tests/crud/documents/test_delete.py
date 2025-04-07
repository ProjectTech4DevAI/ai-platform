import pytest
from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound

from app.crud import DocumentCrud
from app.models import Document

from app.tests.utils.document import DocumentStore

@pytest.fixture
def document(db: Session):
    store = DocumentStore(db)
    document = store.put()

    crud = DocumentCrud(db, document.owner_id)
    crud.delete(document.id)

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

    def test_cannot_delete_others_documents(self, db: Session):
        store = DocumentStore(db)
        document = store.put()
        other_owner_id = store.documents.index.peek()

        crud = DocumentCrud(db, other_owner_id)
        with pytest.raises(NoResultFound):
            crud.delete(document.id)
