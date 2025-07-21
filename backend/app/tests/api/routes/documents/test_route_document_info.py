import pytest
from sqlmodel import Session

from app.tests.utils.document import (
    DocumentComparator,
    DocumentMaker,
    DocumentStore,
    Route,
    WebCrawler,
    crawler,
    httpx_to_standard,
)


@pytest.fixture
def route():
    return Route("info")


class TestDocumentRouteInfo:
    def test_response_is_success(
        self,
        db: Session,
        route: Route,
        crawler: WebCrawler,
    ):
        store = DocumentStore(db)
        response = crawler.get(route.append(store.put()))

        assert response.is_success

    def test_info_reflects_database(
        self,
        db: Session,
        route: Route,
        crawler: WebCrawler,
    ):
        store = DocumentStore(db)
        document = store.put()
        source = DocumentComparator(document)

        target = httpx_to_standard(crawler.get(route.append(document)))

        assert source == target.data

    def test_cannot_info_unknown_document(
        self, db: Session, route: Route, crawler: Route
    ):
        DocumentStore.clear(db)
        maker = DocumentMaker(db)
        response = crawler.get(route.append(next(maker)))

        assert response.is_error
