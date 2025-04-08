import pytest
from sqlmodel import Session, select

from app.models import Document
from app.tests.utils.document import (
    DocumentMaker,
    DocumentStore,
    Route,
    WebCrawler,
    crawler,
)


@pytest.fixture
def route():
    return Route("rm")


class TestDocumentRouteDelete:
    def test_response_is_success(
        self,
        db: Session,
        route: Route,
        crawler: WebCrawler,
    ):
        store = DocumentStore(db)
        response = crawler.get(route.append(store.put()))

        assert response.is_success

    def test_item_is_soft_deleted(
        self,
        db: Session,
        route: Route,
        crawler: WebCrawler,
    ):
        store = DocumentStore(db)
        document = store.put()

        crawler.get(route.append(document))
        db.refresh(document)
        statement = select(Document).where(Document.id == document.id)
        result = db.exec(statement).one()

        assert result.deleted_at is not None

    def test_cannot_delete_unknown_document(
        self,
        db: Session,
        route: Route,
        crawler: WebCrawler,
    ):
        DocumentStore.clear(db)

        maker = DocumentMaker(db)
        response = crawler.get(route.append(next(maker)))

        assert response.is_error
