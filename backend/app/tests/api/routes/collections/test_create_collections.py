import pytest
from uuid import UUID
import io

import openai_responses
from sqlmodel import Session
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.core.config import settings
from app.tests.utils.document import DocumentStore
from app.tests.utils.utils import get_user_from_api_key
from app.main import app
from app.crud.collection import CollectionCrud
from app.seed_data.seed_data import seed_database
from app.models.collection import CollectionStatus
from app.tests.utils.collections_openai_mock import get_mock_openai_client

client = TestClient(app)


@pytest.fixture(scope="function", autouse=True)
def load_seed_data(db):
    """Load seed data before each test."""
    seed_database(db)
    yield


@pytest.fixture(autouse=True)
def mock_s3(monkeypatch):
    class FakeStorage:
        def __init__(self, *args, **kwargs):
            pass

        def upload(self, file_obj, path: str, **kwargs):
            return f"s3://fake-bucket/{path or 'mock-file.txt'}"

        def stream(self, file_obj):
            fake_file = io.BytesIO(b"dummy content")
            fake_file.name = "fake.txt"
            return fake_file

        def get_file_size_kb(self, url: str) -> float:
            return 1.0  # Simulate 1KB files

    class FakeS3Client:
        def head_object(self, Bucket, Key):
            return {"ContentLength": 1024}

    monkeypatch.setattr("app.api.routes.collections.AmazonCloudStorage", FakeStorage)
    monkeypatch.setattr("boto3.client", lambda service: FakeS3Client())


@patch("app.api.routes.collections.configure_openai")
@patch("app.api.routes.collections.get_provider_credential")
class TestCollectionRouteCreate:
    _n_documents = 5

    def test_create_collection_success(
        self,
        mock_get_credential,
        mock_configure_openai,
        client: TestClient,
        db: Session,
    ):
        # Setup test documents
        store = DocumentStore(db)
        documents = store.fill(self._n_documents)
        doc_ids = [str(doc.id) for doc in documents]

        body = {
            "documents": doc_ids,
            "batch_size": 2,
            "model": "gpt-4o",
            "instructions": "Test collection assistant.",
            "temperature": 0.1,
        }
        original_api_key = "ApiKey No3x47A5qoIGhm0kVKjQ77dhCqEdWRIQZlEPzzzh7i8"
        headers = {"X-API-KEY": original_api_key}

        mock_get_credential.return_value = {"api_key": "test_api_key"}

        mock_openai_client = get_mock_openai_client()
        mock_configure_openai.return_value = (mock_openai_client, True)

        response = client.post(
            f"{settings.API_V1_STR}/collections/create",
            json=body,
            headers=headers,
        )

        assert response.status_code == 200
        json = response.json()
        assert json["success"] is True
        metadata = json.get("metadata", {})
        assert metadata["status"] == CollectionStatus.processing.value
        assert UUID(metadata["key"])

        # Confirm collection metadata in DB
        collection_id = UUID(metadata["key"])
        user = get_user_from_api_key(db, headers)
        collection = CollectionCrud(db, user.user_id).read_one(collection_id)

        info_response = client.post(
            f"{settings.API_V1_STR}/collections/info/{collection_id}",
            headers=headers,
        )
        assert info_response.status_code == 200
        info_data = info_response.json()["data"]

        assert collection.status == CollectionStatus.successful.value
        assert collection.owner_id == user.user_id
        assert collection.llm_service_id is not None
        assert collection.llm_service_name == "gpt-4o"
