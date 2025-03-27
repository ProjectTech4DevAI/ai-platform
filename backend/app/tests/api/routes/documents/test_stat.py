import pytest
from sqlmodel import Session

from app.models import Document
from app.tests.utils.document import (
    DocumentComparator,
    DocumentMaker,
    DocumentStore,
    Route,
    WebCrawler,
    crawler,
)

@pytest.fixture
def route():
    return Route('stat')

class TestDocumentRouteStat:
    def test_response_is_success(
            self,
            db: Session,
            route: Route,
            crawler: WebCrawler,
    ):
        store = DocumentStore(db)
        response = crawler.get(route.append(store.put()))

        assert response.is_success

    def test_stat_reflects_database(
            self,
            db: Session,
            route: Route,
            crawler: WebCrawler,
    ):
        store =	DocumentStore(db)
        document = store.put()
        source = DocumentComparator(document)

        target = (crawler
                  .get(route.append(document))
                  .json())

        assert source == target

    def test_cannot_stat_unknown_document(
            self,
            db: Session,
            route: Route,
            crawler: Route,
    ):
        DocumentStore.clear(db)
        maker = DocumentMaker(db)
        response = crawler.get(route.append(next(maker)))

        assert response.is_error
