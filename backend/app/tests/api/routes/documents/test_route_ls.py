import pytest
from sqlmodel import Session

from app.tests.utils.document import (
    DocumentComparator,
    DocumentStore,
    Route,
    WebCrawler,
    crawler,
)


class QueryRoute(Route):
    def pushq(self, key, value):
        qs_args = self.qs_args | {
            key: value,
        }
        return type(self)(self.endpoint, **qs_args)


@pytest.fixture
def route():
    return QueryRoute("ls")


class TestDocumentRouteList:
    def test_response_is_success(self, route: QueryRoute, crawler: WebCrawler):
        response = crawler.get(route)
        assert response.is_success

    def test_empty_db_returns_empty_list(
        self,
        db: Session,
        route: QueryRoute,
        crawler: WebCrawler,
    ):
        DocumentStore.clear(db)
        docs = crawler.get(route).json().get("docs")

        assert not docs

    def test_item_reflects_database(
        self,
        db: Session,
        route: QueryRoute,
        crawler: WebCrawler,
    ):
        store = DocumentStore(db)
        source = DocumentComparator(store.put())
        target = crawler.get(route).json().get("docs").pop()

        assert source == target

    def test_negative_skip_produces_error(
        self,
        route: QueryRoute,
        crawler: WebCrawler,
    ):
        response = crawler.get(route.pushq("skip", -1))
        assert response.is_error

    def test_negative_limit_produces_error(
        self,
        route: QueryRoute,
        crawler: WebCrawler,
    ):
        response = crawler.get(route.pushq("limit", -1))
        assert response.is_error
