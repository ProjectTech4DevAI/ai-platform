from uuid import UUID

import pytest
import openai_responses
from openai import OpenAI
from sqlmodel import Session

from app.crud import CollectionCrud
from app.core.config import settings
from app.tests.utils.document import DocumentStore
from app.tests.utils.collection import get_collection, openai_credentials


def create_and_claim(db: Session):
    store = DocumentStore(db)
    documents = store.fill(1)

    crud = None
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    for _ in range(TestCollectionReadMany._ncollections):
        collection = get_collection(db, client)
        if crud is None:
            crud = CollectionCrud(db, collection.owner_id)
        crud.create(collection, documents)

    return crud.owner_id


@pytest.mark.usefixtures("openai_credentials")
class TestCollectionReadMany:
    _ncollections = 10

    @openai_responses.mock()
    def test_number_read_is_expected(self, db: Session):
        owner = create_and_claim(db)
        crud = CollectionCrud(db, owner)
        docs = crud.read_many()
        assert len(docs) == self._ncollections

    @openai_responses.mock()
    def test_deleted_docs_are_excluded(self, db: Session):
        owner = create_and_claim(db)
        crud = CollectionCrud(db, owner)
        assert all(x.deleted_at is None for x in crud.read_many())

    # @openai_responses.mock()
    # def test_skip_is_respected(self, db: Session):
    #     owner = create_and_claim(db)
    #     crud = CollectionCrud(db, owner)
    #     skip = self._ncollections // 2
    #     docs = crud.read_many(skip=skip)

    #     assert len(docs) == self._ncollections - skip

    # @openai_responses.mock()
    # def test_zero_skip_includes_all(self, db: Session):
    #     owner = create_and_claim(db)
    #     crud = CollectionCrud(db, owner)
    #     docs = crud.read_many(skip=0)
    #     assert len(docs) == self._ncollections

    # @openai_responses.mock()
    # def test_big_skip_is_empty(self, db: Session):
    #     owner = create_and_claim(db)
    #     crud = CollectionCrud(db, owner)
    #     skip = self._ncollections + 1
    #     assert not crud.read_many(skip=skip)

    @openai_responses.mock()
    def test_negative_skip_raises_exception(self, db: Session):
        owner = create_and_claim(db)
        crud = CollectionCrud(db, owner)
        with pytest.raises(ValueError):
            crud.read_many(skip=-1)

    @openai_responses.mock()
    def test_limit_is_respected(self, db: Session):
        owner = create_and_claim(db)
        crud = CollectionCrud(db, owner)
        limit = self._ncollections // 2
        docs = crud.read_many(limit=limit)

        assert len(docs) == limit

    @openai_responses.mock()
    def test_zero_limit_includes_nothing(self, db: Session):
        owner = create_and_claim(db)
        crud = CollectionCrud(db, owner)
        assert not crud.read_many(limit=0)

    @openai_responses.mock()
    def test_negative_limit_raises_exception(self, db: Session):
        owner = create_and_claim(db)
        crud = CollectionCrud(db, owner)
        with pytest.raises(ValueError):
            crud.read_many(limit=-1)

    # @openai_responses.mock()
    # def test_skip_greater_than_limit_is_difference(self, db: Session):
    #     owner = create_and_claim(db)

    #     crud = CollectionCrud(db, owner)
    #     limit = self._ncollections
    #     skip = limit // 2
    #     docs = crud.read_many(skip=skip, limit=limit)

    #     assert len(docs) == limit - skip
