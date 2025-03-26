import functools as ft
from uuid import UUID
from datetime import datetime
from urllib.parse import ParseResult, urlunparse

import pytest
from sqlmodel import Session

from app.models import Document
from app.tests.utils.document import (
    Route,
    WebCrawler,
    crawler,
    insert_document,
    rm_documents,
)

class ListRoute(Route):
    def pushq(self, key, value):
        query = '='.join(map(str, (key, value)))
        return (self
                .to_url()
                ._replace(query=query))

@pytest.fixture
def route():
    return ListRoute('ls')

@pytest.fixture
def document(db: Session):
    return insert_document(db)

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
    def test_response_is_success(self, route: Route, crawler: WebCrawler):
        response = crawler.get(route)
        assert response.is_success

    def test_empty_db_returns_empty_list(
            self,
            db: Session,
            route: Route,
            crawler: WebCrawler,
    ):
        rm_documents(db)
        docs = (crawler
                .get(route)
                .json()
                .get('docs'))

        assert not docs

    def test_item_reflects_database(
            self,
            route: Route,
            crawler: WebCrawler,
            document: Document,
    ):
        source = { x: to_string(y) for (x, y) in dict(document).items() }
        target = (crawler
                  .get(route)
                  .json()
                  .get('docs')
                  .pop())

        assert target == source

    def test_negative_skip_produces_error(
            self,
            route: ListRoute,
            crawler: WebCrawler,
    ):
        url = route.pushq('skip', -1)
        response = crawler.get(urlunparse(url))
        assert response.is_error

    def test_negative_limit_produces_error(
            self,
            route: ListRoute,
            crawler: WebCrawler,
    ):
        url = route.pushq('limit', -1)
        response = crawler.get(urlunparse(url))
        assert response.is_error
