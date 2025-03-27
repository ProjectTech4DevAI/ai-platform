from uuid import UUID

import pytest
from sqlmodel import Session

from app.crud import DocumentCrud

from app.tests.utils.document import (
    DocumentStore,
    int_to_uuid,
)

@pytest.fixture
def crud(db: Session):
    return DocumentCrud(db)

@pytest.fixture
def store(db: Session):
    ds = DocumentStore(db)
    for _ in ds.fill(TestDatabaseReadMany._ndocs):
        pass

    return ds

class TestDatabaseReadMany:
    _ndocs = 10

    def test_number_read_is_expected(
            self,
            crud: DocumentCrud,
            store: DocumentStore,
    ):
        docs = crud.read_many(store.owner)
        assert len(docs) == self._ndocs

    def test_deleted_docs_are_excluded(
            self,
            crud: DocumentCrud,
            store: DocumentStore,
    ):
        assert all(x.deleted_at is None for x in crud.read_many(store.owner))

    def test_skip_is_respected(
            self,
            crud: DocumentCrud,
            store: DocumentStore,
    ):
        skip = self._ndocs // 2
        doc_ids = set(x.id for x in crud.read_many(store.owner, skip=skip))

        for i in range(skip, self._ndocs):
            doc = int_to_uuid(i) # see DocumentMaker
            assert doc in doc_ids

    def test_zero_skip_includes_all(
            self,
            crud: DocumentCrud,
            store: DocumentStore,
    ):
        docs = crud.read_many(store.owner, skip=0)
        assert len(docs) == self._ndocs

    def test_negative_skip_raises_exception(
            self,
            crud: DocumentCrud,
            store: DocumentStore,
    ):
        with pytest.raises(ValueError):
            crud.read_many(store.owner, skip=-1)

    def test_limit_is_respected(
            self,
            crud: DocumentCrud,
            store: DocumentStore,
    ):
        limit = self._ndocs // 2
        docs = crud.read_many(store.owner, limit=limit)

        assert len(docs) == limit

    def test_zero_limit_includes_nothing(
            self,
            crud: DocumentCrud,
            store: DocumentStore,
    ):
        assert not crud.read_many(store.owner, limit=0)

    def test_negative_limit_raises_exception(
            self,
            crud: DocumentCrud,
            store: DocumentStore,
    ):
        with pytest.raises(ValueError):
            crud.read_many(store.owner, limit=-1)
