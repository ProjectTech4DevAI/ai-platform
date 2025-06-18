from unittest.mock import MagicMock, patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.routes.responses import router
from app.models import Project
from app.seed_data.seed_data import seed_database

# Wrap the router in a FastAPI app instance
app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(scope="function", autouse=True)
def load_seed_data(db):
    """Load seed data before each test."""
    seed_database(db)
    yield
    # Cleanup is handled by the db fixture in conftest.py


@patch("app.api.routes.responses.OpenAI")
@patch("app.api.routes.responses.get_provider_credential")
def test_responses_endpoint_success(
    mock_get_credential,
    mock_openai,
    db,
):
    """Test the /responses endpoint for successful response creation."""
    # Setup mock credentials
    mock_get_credential.return_value = {"api_key": "test_api_key"}

    # Setup mock OpenAI client
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # Setup the mock response object with real values for all used fields
    mock_response = MagicMock()
    mock_response.id = "mock_response_id"
    mock_response.output_text = "Test output"
    mock_response.model = "gpt-4o"
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_response.usage.total_tokens = 15
    mock_response.output = []
    mock_client.responses.create.return_value = mock_response

    # Get the Glific project ID (the assistant is created for this project)
    glific_project = db.exec(select(Project).where(Project.name == "Glific")).first()
    if not glific_project:
        pytest.skip("Glific project not found in the database")

    # Use the original API key from seed data (not the encrypted one)
    original_api_key = "ApiKey No3x47A5qoIGhm0kVKjQ77dhCqEdWRIQZlEPzzzh7i8"

    headers = {"X-API-KEY": original_api_key}
    request_data = {
        "project_id": glific_project.id,
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
