from unittest.mock import MagicMock, patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.routes.responses import router
from app.models import Project, OpenAI_Conversation

# Wrap the router in a FastAPI app instance
app = FastAPI()
app.include_router(router)
client = TestClient(app)


@patch("app.api.routes.responses.OpenAI")
@patch("app.api.routes.responses.get_provider_credential")
def test_responses_endpoint_success(
    mock_get_credential, mock_openai, db, normal_user_api_key_headers: dict[str, str]
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
    mock_response.output_text = "Test assistant response"
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

    request_data = {
        "assistant_id": "assistant_glific",
        "question": "What is Glific?",
        "callback_url": "http://example.com/callback",
    }

    response = client.post(
        "/responses", json=request_data, headers=normal_user_api_key_headers
    )
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["success"] is True
    assert response_json["data"]["status"] == "processing"
    assert response_json["data"]["message"] == "Response creation started"


@patch("app.api.routes.responses.OpenAI")
@patch("app.api.routes.responses.get_provider_credential")
@patch("app.api.routes.responses.get_assistant_by_id")
def test_responses_endpoint_without_vector_store(
    mock_get_assistant,
    mock_get_credential,
    mock_openai,
    db,
    normal_user_api_key_headers,
):
    """Test the /responses endpoint when assistant has no vector store configured."""
    # Setup mock credentials
    mock_get_credential.return_value = {"api_key": "test_api_key"}

    # Setup mock assistant without vector store
    mock_assistant = MagicMock()
    mock_assistant.model = "gpt-4"
    mock_assistant.instructions = "Test instructions"
    mock_assistant.temperature = 0.1
    mock_assistant.vector_store_ids = []  # No vector store configured
    mock_get_assistant.return_value = mock_assistant

    # Setup mock OpenAI client
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # Setup the mock response object
    mock_response = MagicMock()
    mock_response.id = "mock_response_id"
    mock_response.output_text = "Test assistant response"
    mock_response.model = "gpt-4"
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_response.usage.total_tokens = 15
    # No output attribute since there are no tool calls
    mock_client.responses.create.return_value = mock_response

    # Get the Glific project ID
    glific_project = db.exec(select(Project).where(Project.name == "Glific")).first()
    if not glific_project:
        pytest.skip("Glific project not found in the database")

    request_data = {
        "assistant_id": "assistant_123",
        "question": "What is Glific?",
        "callback_url": "http://example.com/callback",
    }

    response = client.post(
        "/responses", json=request_data, headers=normal_user_api_key_headers
    )
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["success"] is True
    assert response_json["data"]["status"] == "processing"
    assert response_json["data"]["message"] == "Response creation started"

    # Verify OpenAI client was called without tools
    mock_client.responses.create.assert_called_once_with(
        model=mock_assistant.model,
        previous_response_id=None,
        instructions=mock_assistant.instructions,
        temperature=mock_assistant.temperature,
        input=[{"role": "user", "content": "What is Glific?"}],
    )


@patch("app.api.routes.responses.OpenAI")
@patch("app.api.routes.responses.get_provider_credential")
@patch("app.api.routes.responses.get_assistant_by_id")
@patch("app.api.routes.responses.create_openai_conversation")
def test_responses_endpoint_stores_conversation(
    mock_create_conversation,
    mock_get_assistant,
    mock_get_credential,
    mock_openai,
    db,
):
    """Test that the /responses endpoint stores conversation in database."""
    # Setup mock credentials
    mock_get_credential.return_value = {"api_key": "test_api_key"}

    # Setup mock assistant
    mock_assistant = MagicMock()
    mock_assistant.model = "gpt-4o"
    mock_assistant.instructions = "Test instructions"
    mock_assistant.temperature = 0.1
    mock_assistant.vector_store_id = "vs_test"
    mock_assistant.max_num_results = 20
    mock_get_assistant.return_value = mock_assistant

    # Setup mock OpenAI client
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # Setup the mock response object
    mock_response = MagicMock()
    mock_response.id = "mock_response_id"
    mock_response.output_text = "Test assistant response"
    mock_response.model = "gpt-4o"
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_response.usage.total_tokens = 15
    mock_response.output = []
    mock_client.responses.create.return_value = mock_response

    # Get the Glific project ID
    glific_project = db.exec(select(Project).where(Project.name == "Glific")).first()
    if not glific_project:
        pytest.skip("Glific project not found in the database")

    # Use the original API key from seed data
    original_api_key = "ApiKey No3x47A5qoIGhm0kVKjQ77dhCqEdWRIQZlEPzzzh7i8"

    headers = {"X-API-KEY": original_api_key}
    request_data = {
        "assistant_id": "assistant_123",
        "question": "What is Glific?",
        "callback_url": "http://example.com/callback",
    }

    response = client.post("/responses", json=request_data, headers=headers)
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["success"] is True
    assert response_json["data"]["status"] == "processing"

    # Verify that create_openai_conversation was called with correct data
    mock_create_conversation.assert_called_once()
    call_args = mock_create_conversation.call_args
    conversation_data = call_args[0][1]  # Second argument is the conversation data

    assert conversation_data.response_id == "mock_response_id"
    assert conversation_data.user_question == "What is Glific?"
    assert conversation_data.assistant_response == "Test assistant response"
    assert conversation_data.model == "gpt-4o"
    assert conversation_data.input_tokens == 10
    assert conversation_data.output_tokens == 5
    assert conversation_data.total_tokens == 15
    assert conversation_data.assistant_id == "assistant_123"
    assert conversation_data.project_id == glific_project.id


@patch("app.api.routes.responses.OpenAI")
@patch("app.api.routes.responses.get_provider_credential")
@patch("app.api.routes.responses.get_assistant_by_id")
def test_responses_sync_endpoint_stores_conversation(
    mock_get_assistant,
    mock_get_credential,
    mock_openai,
    db,
):
    """Test that the /responses/sync endpoint stores conversation in database."""
    # Setup mock credentials
    mock_get_credential.return_value = {"api_key": "test_api_key"}

    # Setup mock OpenAI client
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # Setup the mock response object
    mock_response = MagicMock()
    mock_response.id = "mock_response_id"
    mock_response.output_text = "Test assistant response"
    mock_response.model = "gpt-4o"
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_response.usage.total_tokens = 15
    mock_response.output = []
    mock_client.responses.create.return_value = mock_response

    # Get the Glific project ID
    glific_project = db.exec(select(Project).where(Project.name == "Glific")).first()
    if not glific_project:
        pytest.skip("Glific project not found in the database")

    # Use the original API key from seed data
    original_api_key = "ApiKey No3x47A5qoIGhm0kVKjQ77dhCqEdWRIQZlEPzzzh7i8"

    headers = {"X-API-KEY": original_api_key}
    request_data = {
        "model": "gpt-4o",
        "instructions": "Test instructions",
        "vector_store_ids": ["vs_test"],
        "max_num_results": 20,
        "temperature": 0.1,
        "question": "What is Glific?",
    }

    response = client.post("/responses/sync", json=request_data, headers=headers)
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["success"] is True
    assert response_json["data"]["status"] == "success"

    # Verify that conversation was stored in database
    conversation = db.exec(
        select(OpenAI_Conversation).where(
            OpenAI_Conversation.response_id == "mock_response_id"
        )
    ).first()

    assert conversation is not None
    assert conversation.response_id == "mock_response_id"
    assert conversation.user_question == "What is Glific?"
    assert conversation.assistant_response == "Test assistant response"
    assert conversation.model == "gpt-4o"
    assert conversation.input_tokens == 10
    assert conversation.output_tokens == 5
    assert conversation.total_tokens == 15
    assert conversation.assistant_id == "assistant_123"
    assert conversation.project_id == glific_project.id
