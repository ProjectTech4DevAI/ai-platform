import itertools as it
import functools as ft
from uuid import UUID
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from urllib.parse import ParseResult, urlunparse

import pytest
from sqlmodel import Session, delete
from fastapi.testclient import TestClient

from app.core.config import settings
from app.crud.user import get_user_by_email
from app.models import Document

@ft.cache
def get_user_id_by_email(db: Session):
    user = get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    return user.id

@ft.cache
def int_to_uuid(value):
    return UUID(int=value)

def rm_documents(db: Session):
    db.exec(delete(Document))
    db.commit()

def insert_documents(db: Session, n: int):
    documents = DocumentMaker(db)
    for (_, doc) in zip(range(n), documents):
        db.add(doc)
        db.commit()
        db.refresh(doc)
        yield doc

def insert_document(db: Session):
    (document, ) = insert_documents(db, 1)
    return document

class Constants:
    n_documents = 10

class DocumentMaker:
    def __init__(self, db: Session):
        self.owner_id = get_user_id_by_email(db)
        self.index = 0

    def __iter__(self):
        return self

    def __next__(self):
        doc_id = self.get_and_increment()
        args = str(doc_id).split('-')
        fname = Path('/', *args).with_suffix('.xyz')

        return Document(
            id=doc_id,
            owner_id=self.owner_id,
            fname=fname.name,
            object_store_url=fname.as_uri(),
        )

    def get_and_increment(self):
        doc_id = int_to_uuid(self.index)
        self.index += 1
        return doc_id

class Route:
    _empty = ParseResult(*it.repeat('', len(ParseResult._fields)))
    _root = Path(settings.API_V1_STR, 'documents')

    def __init__(self, endpoint, **qs_args):
        self.endpoint = endpoint
        self.qs_args = qs_args

    def __str__(self):
        return urlunparse(self.to_url())

    def to_url(self):
        path = self._root.joinpath(self.endpoint)
        kwargs = {
            'path': str(path),
        }
        if self.qs_args:
            query = '&'.join(it.starmap('{}={}'.format, self.qs_args.items()))
            kwargs['query'] = query

        return self._empty._replace(**kwargs)

    def append(self, doc: Document):
        endpoint = Path(self.endpoint, str(doc.id))
        return type(self)(endpoint, **self.qs_args)

    def pushq(self, key, value):
        qs_args = self.qs_args | {
            key: value,
        }
        return type(self)(self.endpoint, **qs_args)

@dataclass
class WebCrawler:
    client: TestClient
    superuser_token_headers: dict[str, str]

    def get(self, route: Route):
        return self.client.get(
            str(route),
            headers=self.superuser_token_headers,
        )

class DocumentComparator:
    @ft.singledispatchmethod
    @staticmethod
    def to_string(value):
        return value

    @to_string.register
    @staticmethod
    def _(value: UUID):
        return str(value)

    @to_string.register
    @staticmethod
    def _(value: datetime):
        return value.isoformat()

    def __init__(self, document: Document):
        self.document = document

    def __eq__(self, other: dict):
        this = dict(self.to_dict())
        return this == other

    def to_dict(self):
        document = dict(self.document)
        for (k, v) in document.items():
            yield (k, self.to_string(v))

@pytest.fixture(scope='class')
def clean_db_fixture(db: Session):
    rm_documents(db)
    yield
    rm_documents(db)

@pytest.fixture
def crawler(client: TestClient, superuser_token_headers: dict[str, str]):
    return WebCrawler(client, superuser_token_headers)
