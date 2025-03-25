import functools as ft
from uuid import UUID
from datetime import datetime
from urllib.parse import ParseResult, urlunparse

import pytest
from sqlmodel import Session

from app.models import Document
from app.tests.utils.document import Route, crawler, document, rm_documents

@pytest.fixture
def url():
    route = Route('ls')
    return route.to_url()

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
