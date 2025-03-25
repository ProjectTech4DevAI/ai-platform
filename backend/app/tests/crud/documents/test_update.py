import pytest
from sqlmodel import Session

from app.crud import DocumentCrud

from app.tests.utils.document import (
    DocumentMaker,
    clean_db_fixture,
    rm_documents,
)

@pytest.fixture
def documents(db: Session):
    rm_documents(db)
    return DocumentMaker(db)

@pytest.fixture
def crud(db: Session):
    return DocumentCrud(db)

@pytest.mark.usefixtures('clean_db_fixture')
class TestDatabaseUpdate:
    def test_update_adds_one(
            self,
            crud: DocumentCrud,
            documents: DocumentMaker,
    ):
        before = crud.read_many(documents.owner_id)
        crud.update(next(documents))
        after = crud.read_many(documents.owner_id)

        assert len(before) + 1 == len(after)

    def test_sequential_update_is_ordered(
            self,
            crud: DocumentCrud,
            documents: DocumentMaker,
    ):
        (a, b) = (crud.update(y) for (_, y) in zip(range(2), documents))
        assert a.created_at <= b.created_at

    def test_insert_does_not_delete(
            self,
            crud: DocumentCrud,
            documents: DocumentMaker,
    ):
        document = crud.update(next(documents))
        assert document.deleted_at is None
