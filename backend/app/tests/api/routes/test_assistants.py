import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.tests.utils.openai import mock_openai_assistant


@patch("app.api.routes.assistants.fetch_assistant_from_openai")
def test_ingest_assistant_success(
    mock_fetch_assistant,
    client: TestClient,
    normal_user_api_key_headers: dict[str, str],
):
    """Test successful assistant ingestion from OpenAI."""
    mock_assistant = mock_openai_assistant()

    mock_fetch_assistant.return_value = mock_assistant

    response = client.post(
        f"/api/v1/assistant/{mock_assistant.id}/ingest",
        headers=normal_user_api_key_headers,
    )

    assert response.status_code == 201
    response_json = response.json()
    assert response_json["success"] is True
    assert response_json["data"]["assistant_id"] == mock_assistant.id
