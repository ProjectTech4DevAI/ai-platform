from uuid import UUID
from unittest.mock import patch

from fastapi.testclient import TestClient
from unittest.mock import patch

from app.models.collection import Collection, CreationRequest


def test_collection_creation_success(
    client: TestClient, user_api_key_header: dict[str, str]
):
    with patch("app.api.routes.collections.create_service.start_job") as mock_job_start:
        creation_data = CreationRequest(
            model="gpt-4o",
            instructions="string",
            temperature=0.000001,
            documents=[UUID("f3e86a17-1e6f-41ec-b020-5b08eebef928")],
            batch_size=1,
            callback_url=None,
        )

        resp = client.post(
            "/api/v1/collections/create",
            json=creation_data.model_dump(mode="json"),
            headers=user_api_key_header,
        )

        assert resp.status_code == 200
        body = resp.json()

        assert body["success"] is True
        assert body["data"] is None

        assert body["metadata"]["status"] == "processing"
        assert body["metadata"]["route"] == "/collections/create"
        assert body["metadata"]["key"] is not None
        job_key = UUID(body["metadata"]["key"])

        mock_job_start.assert_called_once()
        kwargs = mock_job_start.call_args.kwargs

        assert "db" in kwargs
        assert kwargs["request"] == creation_data.model_dump()
        assert kwargs["payload"]["status"] == "processing"

        assert kwargs["collection_job_id"] == job_key
