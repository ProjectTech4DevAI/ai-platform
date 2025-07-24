import pytest
import openai_responses
from openai_responses import OpenAIMock
from openai import OpenAI
from sqlmodel import Session, select
from unittest.mock import patch

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
    return Route("remove")


class TestDocumentRouteRemove:
    @openai_responses.mock()
    @patch("app.api.routes.documents.get_openai_client")
    def test_response_is_success(
        self,
        mock_get_openai_client,
        db: Session,
        route: Route,
        crawler: WebCrawler,
    ):
        openai_mock = OpenAIMock()
        with openai_mock.router:
            client = OpenAI(api_key="sk-test-key")
            mock_get_openai_client.return_value = client

            store = DocumentStore(db)
            response = crawler.get(route.append(store.put()))

            assert response.is_success

    @openai_responses.mock()
    @patch("app.api.routes.documents.get_openai_client")
    def test_item_is_soft_removed(
        self,
        mock_get_openai_client,
        db: Session,
        route: Route,
        crawler: WebCrawler,
    ):
        openai_mock = OpenAIMock()
        with openai_mock.router:
            client = OpenAI(api_key="sk-test-key")
            mock_get_openai_client.return_value = client

            store = DocumentStore(db)
            document = store.put()

            crawler.get(route.append(document))
            db.refresh(document)
            statement = select(Document).where(Document.id == document.id)
            result = db.exec(statement).one()

            assert result.deleted_at is not None

    @openai_responses.mock()
    @patch("app.api.routes.documents.get_openai_client")
    def test_cannot_remove_unknown_document(
        self,
        mock_get_openai_client,
        db: Session,
        route: Route,
        crawler: WebCrawler,
    ):
        openai_mock = OpenAIMock()
        with openai_mock.router:
            client = OpenAI(api_key="sk-test-key")
            mock_get_openai_client.return_value = client

            DocumentStore.clear(db)
            maker = DocumentMaker(db)
            response = crawler.get(route.append(next(maker)))

            assert response.is_error
