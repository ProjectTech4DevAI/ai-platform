from pathlib import Path
from urllib.parse import ParseResult, urlunparse

import pytest
from sqlmodel import Session, select
from fastapi.testclient import TestClient

from app.models import Document
from app.core.config import settings
from app.tests.utils.document import (
    DocumentMaker,
    Route,
    crawler,
    insert_document,
    rm_documents,
)

class DeletedRoute(Route):
    def update(self, doc: Document):
        endpoint = Path(self.endpoint, str(doc.id))
        return type(self)(endpoint)

@pytest.fixture
def route():
    return DeletedRoute('rm')

@pytest.fixture
def document(db: Session):
    rm_documents(db)
    return insert_document(db)

class TestDocumentRouteDelete:
    def test_response_is_success(
            self,
            db: Session,
            route: DeletedRoute,
            crawler: Route,
            document: Document,
    ):
        response = crawler.get(route.update(document))
        assert response.is_success

    def test_item_is_soft_deleted(
            self,
            db: Session,
            route: DeletedRoute,
            crawler: Route,
            document: Document,
    ):
        crawler.get(route.update(document))

        statement = (
            select(Document)
            .where(Document.id == document.id)
        )
        result = db.exec(statement).one()

        return result.deleted_at is not None

    def test_cannot_delete_unknown_document(
            self,
            db: Session,
            route: DeletedRoute,
            crawler: Route,
    ):
        rm_documents(db)
        maker = DocumentMaker(db)
        response = crawler.get(route.update(next(maker)))
        assert response.is_error
