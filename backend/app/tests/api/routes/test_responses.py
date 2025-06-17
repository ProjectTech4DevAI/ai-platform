from unittest.mock import MagicMock, patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.routes.responses import router
from app.models import APIKey, Assistant
from app.crud.assistants import get_assistant_by_id
from app.crud.credentials import get_provider_credential

# Wrap the router in a FastAPI app instance
app = FastAPI()
app.include_router(router)
client = TestClient(app)


@patch("app.api.routes.responses.OpenAI")
@patch("app.api.routes.responses.get_assistant_by_id")
@patch("app.api.routes.responses.get_provider_credential")
def test_responses_endpoint_success(
    mock_get_credential,
    mock_get_assistant,
    mock_openai,
    db,
):
    """Test the /responses endpoint for successful response creation."""
    # Setup mock assistant
    mock_assistant = MagicMock()
    mock_assistant.project_id = 1
    mock_assistant.model = "gpt-4o"
    mock_assistant.instructions = "Test instructions"
    mock_assistant.vector_store_id = "vs_123"
    mock_assistant.max_num_results = 20
    mock_assistant.temperature = 0.1
    mock_get_assistant.return_value = mock_assistant

    # Setup mock credentials
    mock_get_credential.return_value = {"api_key": "test_api_key"}

    # Setup mock OpenAI client
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # Get API key
    api_key_record = db.exec(select(APIKey).where(APIKey.is_deleted is False)).first()
    if not api_key_record:
        pytest.skip("No API key found in the database for testing")

    headers = {"X-API-KEY": api_key_record.key}
    request_data = {
        "project_id": 1,
        "assistant_id": "assistant_123",
        "question": "What is Glific?",
        "callback_url": "http://example.com/callback",
    }

    response = client.post("/responses", json=request_data, headers=headers)
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["success"] is True
    assert response_json["data"]["status"] == "processing"
    assert response_json["data"]["message"] == "Response creation started"
