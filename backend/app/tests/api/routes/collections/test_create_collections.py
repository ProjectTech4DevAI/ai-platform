from uuid import UUID

from fastapi.testclient import TestClient
from unittest.mock import patch

from app.models.collection import Collection, CollectionStatus, CreationRequest


def test_collection_creation_success(
    client: TestClient, user_api_key_header: dict[str, str]
):
    with patch(
        "app.api.routes.collections.create_services.start_job"
    ) as mock_job_start:
        creation_data = CreationRequest(
            model="gpt-4o",
            instructions="string",
            temperature=0.000001,
            documents=[UUID("f3e86a17-1e6f-41ec-b020-5b08eebef928")],
            batch_size=1,
            callback_url=None,
        )

        api_response = client.post(
            "/api/v1/collections/create",
            json=creation_data.model_dump(mode="json"),
            headers=user_api_key_header,
        )

        assert api_response.status_code == 200
        response_body = api_response.json()

        assert response_body["success"] is True
        assert response_body["metadata"]["status"] == "processing"
        assert response_body["metadata"]["key"] is not None
        assert UUID(response_body["metadata"]["key"])  # Verify UUID format
        assert response_body["data"] is None

        mock_job_start.assert_called_once()
        job_args = mock_job_start.call_args[1]
        assert job_args["request"] == creation_data.model_dump()
        assert job_args["payload"]["status"] == "processing"
        assert isinstance(job_args["collection"], Collection)
        assert job_args["collection"].status == CollectionStatus.processing
        assert job_args["project_id"] == job_args["collection"].project_id
        assert job_args["organization_id"] == job_args["collection"].organization_id
