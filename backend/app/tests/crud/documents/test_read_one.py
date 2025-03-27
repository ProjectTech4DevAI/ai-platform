import pytest
from sqlmodel import Session
from sqlalchemy.exc import NoResultFound

from app.crud import DocumentCrud

from app.tests.utils.document import DocumentStore

@pytest.fixture
def store(db: Session):
    return DocumentStore(db)

class TestDatabaseReadOne:
    def test_can_select_valid_id(self, db: Session, store: DocumentStore):
        document = store.put()

        crud = DocumentCrud(db)
        result = crud.read_one(document.id)

        assert result.id == document.id

    def test_cannot_select_invalid_id(self, db: Session, store: DocumentStore):
        document = next(store.maker)

        crud = DocumentCrud(db)
        with pytest.raises(NoResultFound):
            crud.read_one(document.id)
