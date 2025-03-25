import logging
import itertools as it
import functools as ft
from uuid import UUID
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from urllib.parse import ParseResult, urlunparse

import pytest
from sqlmodel import Session
from fastapi.testclient import TestClient

from app.models import Document
from app.core.config import settings
from app.tests.utils.document import insert_document, rm_documents

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

@pytest.fixture
def url():
    route = Route('ls')
    return route.to_url()

@pytest.fixture
def document(db: Session):
    return insert_document(db)

@pytest.fixture
def crawler(client: TestClient, superuser_token_headers: dict[str, str]):
    return WebCrawler(client, superuser_token_headers)

@ft.singledispatch
def to_string(value):
    return value

@to_string.register
def _(value: UUID):
    return str(value)

@to_string.register
def _(value: datetime):
    return value.isoformat()

class TestDocumentRouteList:
    def test_response_is_success(self, url: ParseResult, crawler: Route):
        response = crawler.get(url)
        assert response.is_success

    def test_empty_db_returns_empty_list(
            self,
            db: Session,
            url: ParseResult,
            crawler: Route,
    ):
        rm_documents(db)
        docs = (crawler
                .get(url)
                .json()
                .get('docs'))

        assert not docs

    def test_item_reflects_database(
            self,
            url: ParseResult,
            document: Document,
            crawler: Route,
    ):
        source = { x: to_string(y) for (x, y) in dict(document).items() }
        target = (crawler
                  .get(url)
                  .json()
                  .get('docs')
                  .pop())

        assert target == source

    def test_negative_skip_produces_error(
            self,
            url: ParseResult,
            crawler: Route,
    ):
        target = url._replace(query='skip=-1')
        response = crawler.get(urlunparse(target))
        assert response.is_error

    def test_negative_limit_produces_error(
            self,
            url: ParseResult,
            crawler: Route,
    ):
        target = url._replace(query='limit=-1')
        response = crawler.get(urlunparse(target))
        assert response.is_error
