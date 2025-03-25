import pytest
from sqlmodel import Session

from app.crud import DocumentCrud

from _utils import (
    Constants,
    clean_db_fixture,
    get_user_id_by_email,
    insert_documents,
    int_to_uuid,
    rm_documents,
)

@pytest.fixture
def document_collection(db: Session):
    rm_documents(db)
    return list(insert_documents(db, Constants.n_documents))

@pytest.mark.usefixtures('clean_db_fixture')
class TestDatabaseReadMany:
    def test_number_read_is_expected(
            self,
            db: Session,
            document_collection: list,
    ):
        crud = DocumentCrud(db)
        owner_id = get_user_id_by_email(db)
        documents = crud.read_many(owner_id)

        assert len(documents) == Constants.n_documents

    def test_deleted_docs_excluded(
            self,
            db: Session,
            document_collection: list,
    ):
        assert all(x.deleted_at is None for x in document_collection)

    def test_skip_is_respected(
            self,
            db: Session,
            document_collection: list,
    ):
        crud = DocumentCrud(db)
        owner_id = get_user_id_by_email(db)
        skip = Constants.n_documents // 2
        doc_ids = set(x.id for x in crud.read_many(owner_id, skip=skip))

        for i in range(skip, Constants.n_documents):
            doc = int_to_uuid(i)
            assert doc in doc_ids

    def test_zero_skip_includes_all(
            self,
            db: Session,
            document_collection: list,
    ):
        crud = DocumentCrud(db)
        owner_id = get_user_id_by_email(db)
        documents = crud.read_many(owner_id, skip=0)

        assert len(documents) == Constants.n_documents

    def test_negative_skip_raises_exception(
            self,
            db: Session,
            document_collection: list,
    ):
        crud = DocumentCrud(db)
        owner_id = get_user_id_by_email(db)
        with pytest.raises(ValueError):
            crud.read_many(owner_id, skip=-1)

    def test_limit_is_respected(
            self,
            db: Session,
            document_collection: list,
    ):
        crud = DocumentCrud(db)
        owner_id = get_user_id_by_email(db)
        limit = Constants.n_documents // 2
        documents = crud.read_many(owner_id, limit=limit)

        assert len(documents) == limit

    def test_zero_limit_includes_none(
            self,
            db: Session,
            document_collection: list,
    ):
        crud = DocumentCrud(db)
        owner_id = get_user_id_by_email(db)
        documents = crud.read_many(owner_id, limit=0)

        assert not documents

    def test_negative_limit_raises_exception(
            self,
            db: Session,
            document_collection: list,
    ):
        crud = DocumentCrud(db)
        owner_id = get_user_id_by_email(db)
        with pytest.raises(ValueError):
            crud.read_many(owner_id, limit=-1)
