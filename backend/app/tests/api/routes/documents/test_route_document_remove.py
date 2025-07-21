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
from app.seed_data.seed_data import seed_database
from app.tests.utils.utils import openai_credentials


@pytest.fixture(scope="function", autouse=True)
def load_seed_data(db):
    """Load seed data before each test."""
    seed_database(db)
    yield


@pytest.fixture
def route():
    return Route("remove")


@pytest.mark.usefixtures("openai_credentials")
class TestDocumentRouteRemove:
    @openai_responses.mock()
    @patch("app.api.routes.documents.get_provider_credential")
    @patch("app.api.routes.documents.configure_openai")
    def test_response_is_success(
        self,
        mock_configure_openai,
        mock_get_credential,
        db: Session,
        route: Route,
        crawler: WebCrawler,
    ):
        openai_mock = OpenAIMock()
        with openai_mock.router:
            client = OpenAI(api_key="test_key")
            mock_get_credential.return_value = {"api_key": "sk-test-key"}
            mock_configure_openai.return_value = (client, True)

            store = DocumentStore(db)
            response = crawler.get(route.append(store.put()))

            assert response.is_success

    @openai_responses.mock()
    @patch("app.api.routes.documents.get_provider_credential")
    @patch("app.api.routes.documents.configure_openai")
    def test_item_is_soft_removed(
        self,
        mock_configure_openai,
        mock_get_credential,
        db: Session,
        route: Route,
        crawler: WebCrawler,
    ):
        openai_mock = OpenAIMock()
        with openai_mock.router:
            mock_get_credential.return_value = {"api_key": "test-key"}
            client = OpenAI(api_key="test_key")
            mock_configure_openai.return_value = (client, True)

            store = DocumentStore(db)
            document = store.put()

            crawler.get(route.append(document))
            db.refresh(document)
            statement = select(Document).where(Document.id == document.id)
            result = db.exec(statement).one()

            assert result.deleted_at is not None

    @openai_responses.mock()
    @patch("app.api.routes.documents.get_provider_credential")
    @patch("app.api.routes.documents.configure_openai")
    def test_cannot_remove_unknown_document(
        self,
        mock_configure_openai,
        mock_get_credential,
        db: Session,
        route: Route,
        crawler: WebCrawler,
    ):
        openai_mock = OpenAIMock()
        with openai_mock.router:
            client = OpenAI(api_key="test_key")
            mock_get_credential.return_value = {"api_key": "sk-test-key"}
            mock_configure_openai.return_value = (client, True)

            DocumentStore.clear(db)
            maker = DocumentMaker(db)
            response = crawler.get(route.append(next(maker)))

            assert response.is_error
