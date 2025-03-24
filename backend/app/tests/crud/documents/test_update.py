import pytest
from sqlmodel import Session

from app.crud import DocumentCrud

from _utils import (
    DocumentMaker,
    rm_documents,
)

class TestState:
    def __init__(self, db: Session):
        self.crud = DocumentCrud(db)
        self.documents = DocumentMaker(db)

    def add(self):
        return self.crud.update(next(self.documents))

    def get(self):
        return self.crud.read_many(self.documents.owner_id)

@pytest.fixture
def state(db: Session):
    rm_documents(db)
    return TestState(db)

class TestDatabaseUpdate:
    def test_update_adds_one(self, state: TestState):
        before = state.get()
        state.add()
        after = state.get()

        assert len(before) + 1 == len(after)

    def test_sequential_update_is_ordered(self, state: TestState):
        (a, b) = (state.add() for _ in range(2))
        assert a.created_at <= b.created_at

    def test_insert_does_not_delete(self, state: TestState):
        document = state.add()
        assert document.deleted_at is None
