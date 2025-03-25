import itertools as it
import functools as ft
from uuid import UUID
from pathlib import Path
from dataclasses import dataclass
from urllib.parse import ParseResult, urlunparse

import pytest
from sqlmodel import Session, delete
from fastapi.testclient import TestClient

from app.core.config import settings
from app.crud.user import get_user_by_email
from app.models import Document

@ft.cache
def get_user_id_by_email(session: Session):
    user = get_user_by_email(session=session, email=settings.FIRST_SUPERUSER)
    return user.id

@ft.cache
def int_to_uuid(value):
    return UUID(int=value)

def rm_documents(session: Session):
    session.exec(delete(Document))
    session.commit()

def insert_documents(session: Session, n: int):
    documents = DocumentMaker(session)
    for (_, doc) in zip(range(n), documents):
        session.add(doc)
        session.commit()
        session.refresh(doc)
        yield doc

def insert_document(session: Session):
    (document, ) = insert_documents(session, 1)
    return document

class Constants:
    n_documents = 10

class DocumentMaker:
    def __init__(self, session: Session):
        self.owner_id = get_user_id_by_email(session)
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

    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.root = Path(settings.API_V1_STR, 'documents')

    def __str__(self):
        return urlunparse(self.to_url())

    def to_url(self):
        path = self.root.joinpath(self.endpoint)
        return self._empty._replace(path=str(path))

@dataclass
class WebCrawler:
    client: TestClient
    superuser_token_headers: dict[str, str]

    @ft.singledispatchmethod
    def get(self, route: str):
        return self.client.get(route, headers=self.superuser_token_headers)

    @get.register
    def _(self, route: Route):
        return self.get(str(route))

    @get.register
    def _(self, route: ParseResult):
        return self.get(urlunparse(route))

@pytest.fixture(scope='class')
def clean_db_fixture(db: Session):
    rm_documents(db)
    yield
    rm_documents(db)

@pytest.fixture
def document(db: Session):
    return insert_document(db)

@pytest.fixture
def crawler(client: TestClient, superuser_token_headers: dict[str, str]):
    return WebCrawler(client, superuser_token_headers)
