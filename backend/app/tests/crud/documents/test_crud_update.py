import pytest
from sqlmodel import Session

from app.crud import DocumentCrud

from app.tests.utils.document import DocumentMaker, DocumentStore


@pytest.fixture
def documents(db: Session):
    store = DocumentStore(db)
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

        assert a.created_at <= b.created_at

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
