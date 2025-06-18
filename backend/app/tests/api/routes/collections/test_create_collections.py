import pytest
import asyncio
import io
from openai import OpenAIError
import openai_responses
from uuid import UUID
from httpx import AsyncClient
from sqlmodel import Session
from app.core.config import settings
from app.tests.utils.document import DocumentStore
from app.tests.utils.utils import openai_credentials


# Automatically mock AmazonCloudStorage for all tests
@pytest.fixture(autouse=True)
def mock_s3(monkeypatch):
    class FakeStorage:
        def __init__(self, *args, **kwargs):
            pass

        def upload(self, file_obj, path: str, **kwargs):
            # Return a dummy path (this is fine)
            return f"s3://fake-bucket/{path or 'mock-file'}"

        def stream(self, file_obj):
            # Wrap in a file-like object that has a `.name` attribute
            fake_file = io.BytesIO(b"dummy content")
            fake_file.name = "fake.txt"
            return fake_file

    monkeypatch.setattr("app.api.routes.collections.AmazonCloudStorage", FakeStorage)


@pytest.mark.usefixtures("openai_credentials")
class TestCollectionRouteCreate:
    _n_documents = 5

    @pytest.mark.asyncio
    @openai_responses.mock()
    async def test_create_collection_success(
        self,
        async_client: AsyncClient,
        db: Session,
        superuser_token_headers: dict[str, str],
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

        response = await async_client.post(
            f"{settings.API_V1_STR}/collections/create",
            json=body,
            headers=superuser_token_headers,
        )

        assert response.status_code == 200
        json = response.json()
        assert json["success"] is True
        metadata = json.get("metadata", {})
        assert metadata["status"] == "processing"
        assert UUID(metadata["key"])

    @pytest.mark.asyncio
    async def test_create_collection_timeout(
        self,
        async_client: AsyncClient,
        db: Session,
        superuser_token_headers: dict[str, str],
        monkeypatch,
    ):
        async def long_task(*args, **kwargs):
            await asyncio.sleep(30)  # exceed timeout
            return None

        monkeypatch.setattr(
            "app.api.routes.collections.do_create_collection",  # adjust if necessary
            long_task,
        )

        body = {
            "documents": [],
            "batch_size": 1,
            "model": "gpt-4o",
            "instructions": "Slow task",
            "temperature": 0.2,
        }

        response = await async_client.post(
            f"{settings.API_V1_STR}/collections/create",
            json=body,
            headers=superuser_token_headers,
        )

        assert response.status_code == 408
        json = response.json()
        assert json["success"] is False
        assert json["data"] is None
        assert json["error"] == "The task timed out."
        assert json["metadata"] is None
