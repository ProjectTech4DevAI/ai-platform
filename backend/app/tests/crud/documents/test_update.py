import pytest
from uuid import UUID
from typing import ClassVar
from sqlmodel import Session
from dataclasses import dataclass

from app.crud import DocumentCrud
from app.core.config import settings

from _utils import (
    Constants,
    get_user_id_by_email,
    insert_documents,
    int_to_uuid,
    mk_document,
    rm_documents,
)

@dataclass
class State:
    crud: DocumentCrud
    owner_id: UUID
    doc_id: ClassVar[int] = 0

    def add(self):
        document = mk_document(self.owner_id, self.doc_id)
        self.doc_id += 1

        return self.crud.update(document)

    def get(self):
        return self.crud.read_many(self.owner_id)

@pytest.fixture
def state(db: Session):
    rm_documents(db)

    crud = DocumentCrud(db)
    owner_id = get_user_id_by_email(db)

    return State(crud, owner_id)

class TestDatabaseUpdate:
    def test_update_adds_one(self, state: State):
        before = state.get()
        state.add()
        after = state.get()

        assert len(before) + 1 == len(after)

    def test_sequential_update_is_ordered(self, state: State):
        (a, b) = map(state.add, range(2))
        assert a.create_at >= b.created_at

    def test_sequential_update_is_ordered(self, state: State):
        document = state.add()
        assert document.deleted_at is None
