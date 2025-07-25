import pytest
from sqlmodel import Session
from sqlalchemy.exc import NoResultFound

from app.crud import DocumentCrud

from app.tests.utils.document import DocumentStore
from app.core.exception_handlers import HTTPException


@pytest.fixture
def store(db: Session):
    return DocumentStore(db)


class TestDatabaseReadOne:
    def test_can_select_valid_id(self, db: Session, store: DocumentStore):
        document = store.put()

        crud = DocumentCrud(db, store.owner)
        result = crud.read_one(document.id)

        assert result.id == document.id

    def test_cannot_select_invalid_id(self, db: Session, store: DocumentStore):
        document = next(store.documents)

        crud = DocumentCrud(db, store.owner)

        with pytest.raises(HTTPException) as exc_info:
            crud.read_one(document.id)

        assert exc_info.value.status_code == 404
        assert "Document not found" in str(exc_info.value.detail)

    def test_cannot_read_others_documents(self, db: Session, store: DocumentStore):
        document = store.put()
        other = DocumentStore(db)

        crud = DocumentCrud(db, other.owner)
        with pytest.raises(HTTPException) as exc_info:
            crud.read_one(document.id)

        assert exc_info.value.status_code == 404
        assert "Document not found" in str(exc_info.value.detail)
