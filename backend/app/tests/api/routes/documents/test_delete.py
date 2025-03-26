import pytest
from sqlmodel import Session, select

from app.models import Document
from app.tests.utils.document import (
    DocumentMaker,
    Route,
    WebCrawler,
    crawler,
    insert_document,
    rm_documents,
)

@pytest.fixture
def route():
    return Route('rm')

@pytest.fixture
def document(db: Session):
    rm_documents(db)
    return insert_document(db)

class TestDocumentRouteDelete:
    def test_response_is_success(
            self,
            route: Route,
            crawler: WebCrawler,
            document: Document,
    ):
        response = crawler.get(route.append(document))
        assert response.is_success

    def test_item_is_soft_deleted(
            self,
            db: Session,
            route: Route,
            crawler: WebCrawler,
            document: Document,
    ):
        crawler.get(route.append(document))

        statement = (
            select(Document)
            .where(Document.id == document.id)
        )
        result = db.exec(statement).one()

        return result.deleted_at is not None

    def test_cannot_delete_unknown_document(
            self,
            db: Session,
            route: Route,
            crawler: WebCrawler,
    ):
        rm_documents(db)
        maker = DocumentMaker(db)
        response = crawler.get(route.append(next(maker)))
        assert response.is_error
