import pytest
from sqlmodel import Session
from sqlalchemy.exc import NoResultFound

from app.crud import DocumentCrud

from app.tests.utils.document import (
    clean_db_fixture,
    insert_document,
    int_to_uuid,
    rm_documents,
)

@pytest.fixture
def clean_db_fixture(db: Session):
    rm_documents(db)
    yield
    rm_documents(db)

@pytest.mark.usefixtures('clean_db_fixture')
class TestDatabaseReadOne:
    def test_can_select_valid_id(
            self,
            db: Session,
            clean_db_fixture: None,
    ):
        crud = DocumentCrud(db)
        document = insert_document(db)
        result = crud.read_one(document.id)

        assert result.id == document.id

    def test_cannot_select_invalid_id(
            self,
            db: Session,
            clean_db_fixture: None,
    ):
        crud = DocumentCrud(db)
        document_id = int_to_uuid(0)
        with pytest.raises(NoResultFound):
            crud.read_one(document_id)
