import pytest
from uuid import UUID
import io

import openai_responses
from sqlmodel import Session
from fastapi.testclient import TestClient

from app.core.config import settings
from app.tests.utils.document import DocumentStore
from app.tests.utils.utils import openai_credentials, get_user_from_api_key
from app.main import app
from app.crud.collection import CollectionCrud
from app.models.collection import CollectionStatus

client = TestClient(app)


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


@pytest.mark.usefixtures("openai_credentials")
class TestCollectionRouteCreate:
    _n_documents = 5

    @openai_responses.mock()
    def test_create_collection_success(
        self,
        client: TestClient,
        db: Session,
    ):
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
