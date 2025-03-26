import logging
from pathlib import Path
from urllib.parse import ParseResult, urlunparse

import pytest
from sqlmodel import Session, select
from fastapi.testclient import TestClient

from app.models import Document
from app.core.config import settings
from app.tests.utils.document import (
    DocumentComparator,
    DocumentMaker,
    Route,
    WebCrawler,
    crawler,
    insert_document,
    rm_documents,
)

@pytest.fixture
def route():
    return Route('stat')

@pytest.fixture
def document(db: Session):
    rm_documents(db)
    return insert_document(db)

class TestDocumentRouteStat:
    def test_response_is_success(
            self,
            route: Route,
            crawler: WebCrawler,
            document: Document,
    ):
        response = crawler.get(route.append(document))
        assert response.is_success

    def test_stat_reflects_database(
            self,
            route: Route,
            crawler: WebCrawler,
            document: Document,
    ):
        target = (crawler
                  .get(route.append(document))
                  .json())
        logging.critical(target)
        source = DocumentComparator(document)

        assert source == target

    def test_cannot_stat_unknown_document(
            self,
            db: Session,
            route: Route,
            crawler: Route,
    ):
        rm_documents(db)
        maker = DocumentMaker(db)
        response = crawler.get(route.append(next(maker)))
        assert response.is_error
