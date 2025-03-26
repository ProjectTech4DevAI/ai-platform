import pytest
from sqlmodel import Session

from app.models import Document
from app.tests.utils.document import (
    DocumentComparator,
    Route,
    WebCrawler,
    crawler,
    insert_document,
    rm_documents,
)

@pytest.fixture
def route():
    return Route('ls')

@pytest.fixture
def document(db: Session):
    return insert_document(db)

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
        target = (crawler
                  .get(route)
                  .json()
                  .get('docs')
                  .pop())
        source = DocumentComparator(document)

        assert source == target

    def test_negative_skip_produces_error(
            self,
            route: Route,
            crawler: WebCrawler,
    ):
        response = crawler.get(route.pushq('skip', -1))
        assert response.is_error

    def test_negative_limit_produces_error(
            self,
            route: Route,
            crawler: WebCrawler,
    ):
        response = crawler.get(route.pushq('limit', -1))
        assert response.is_error
