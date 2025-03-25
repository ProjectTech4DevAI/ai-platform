from uuid import UUID

import pytest
from sqlmodel import Session

from app.crud import DocumentCrud

from app.tests.utils.document import (
    Constants,
    clean_db_fixture,
    get_user_id_by_email,
    insert_documents,
    int_to_uuid,
    rm_documents,
)

class DocumentManager:
    def __init__(self, db: Session):
        self.db = db
        self.documents = None

        rm_documents(self.db)

    def __iter__(self):
        if self.documents is None:
            raise AttributeError()
        yield from self.documents

    def add(self, n):
        self.documents = list(insert_documents(self.db, n))

@pytest.fixture
def documents(db: Session):
    return DocumentManager(db)

@pytest.fixture
def crud(db: Session):
    return DocumentCrud(db)

@pytest.fixture
def owner_id(db: Session):
    return get_user_id_by_email(db)

@pytest.mark.usefixtures('clean_db_fixture')
class TestDatabaseReadMany:
    def test_number_read_is_expected(
            self,
            crud: DocumentCrud,
            owner_id: UUID,
            documents: DocumentManager,
    ):
        documents.add(Constants.n_documents)
        docs = crud.read_many(owner_id)
        assert len(docs) == Constants.n_documents

    def test_deleted_docs_are_excluded(self, documents: DocumentManager):
        documents.add(Constants.n_documents)
        assert all(x.deleted_at is None for x in documents)

    def test_skip_is_respected(
            self,
            crud: DocumentCrud,
            owner_id: UUID,
            documents: DocumentManager,
    ):
        documents.add(Constants.n_documents)
        skip = Constants.n_documents // 2
        doc_ids = set(x.id for x in crud.read_many(owner_id, skip=skip))

        for i in range(skip, Constants.n_documents):
            doc = int_to_uuid(i)
            assert doc in doc_ids

    def test_zero_skip_includes_all(
            self,
            crud: DocumentCrud,
            owner_id: UUID,
            documents: DocumentManager,
    ):
        documents.add(Constants.n_documents)
        docs = crud.read_many(owner_id, skip=0)
        assert len(docs) == Constants.n_documents

    def test_negative_skip_raises_exception(
            self,
            crud: DocumentCrud,
            owner_id: UUID,
    ):
        with pytest.raises(ValueError):
            crud.read_many(owner_id, skip=-1)

    def test_limit_is_respected(
            self,
            crud: DocumentCrud,
            owner_id: UUID,
            documents: DocumentManager,
    ):
        documents.add(Constants.n_documents)
        limit = Constants.n_documents // 2
        docs = crud.read_many(owner_id, limit=limit)

        assert len(docs) == limit

    def test_zero_limit_includes_nothing(
            self,
            crud: DocumentCrud,
            owner_id: UUID,
            documents: DocumentManager,
    ):
        documents.add(Constants.n_documents)
        docs = crud.read_many(owner_id, limit=0)
        assert not docs

    def test_negative_limit_raises_exception(
            self,
            crud: DocumentCrud,
            owner_id: UUID,
    ):
        with pytest.raises(ValueError):
            crud.read_many(owner_id, limit=-1)
