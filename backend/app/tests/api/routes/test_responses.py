from unittest.mock import MagicMock, patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import select
import openai

from app.api.routes.responses import router
from app.models import Project

# Wrap the router in a FastAPI app instance
app = FastAPI()
app.include_router(router)
client = TestClient(app)


@patch("app.api.routes.responses.OpenAI")
@patch("app.api.routes.responses.get_provider_credential")
@patch("app.api.routes.responses.get_assistant_by_id")
@patch("app.api.routes.responses.LangfuseTracer")
@patch("app.api.routes.responses.get_ancestor_id_from_response")
@patch("app.api.routes.responses.create_conversation")
@patch("app.api.routes.responses.get_conversation_by_ancestor_id")
def test_responses_endpoint_success(
    mock_get_conversation_by_ancestor_id,
    mock_create_conversation,
    mock_get_ancestor_id_from_response,
    mock_tracer_class,
    mock_get_assistant,
    mock_get_credential,
    mock_openai,
    db,
    user_api_key_header: dict[str, str],
):
    """Test the /responses endpoint for successful response creation."""

    # Setup mock credentials - configure to return different values based on provider
    def mock_get_credentials_by_provider(*args, **kwargs):
        provider = kwargs.get("provider")
        if provider == "openai":
            return {"api_key": "test_api_key"}
        elif provider == "langfuse":
            return {
                "public_key": "test_public_key",
                "secret_key": "test_secret_key",
                "host": "https://cloud.langfuse.com",
            }
        return None

    mock_get_credential.side_effect = mock_get_credentials_by_provider

    # Setup mock assistant
    mock_assistant = MagicMock()
    mock_assistant.model = "gpt-4o"
    mock_assistant.instructions = "Test instructions"
    mock_assistant.temperature = 0.1
    mock_assistant.vector_store_ids = ["vs_test"]
    mock_assistant.max_num_results = 20

    # Configure mock to return the assistant for any call
    def return_mock_assistant(*args, **kwargs):
        return mock_assistant

    mock_get_assistant.side_effect = return_mock_assistant

    # Setup mock OpenAI client
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # Setup the mock response object with proper response ID format
    mock_response = MagicMock()
    mock_response.id = "resp_1234567890abcdef1234567890abcdef1234567890"
    mock_response.output_text = "Test output"
    mock_response.model = "gpt-4o"
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_response.usage.total_tokens = 15
    mock_response.output = []
    mock_response.previous_response_id = None
    mock_client.responses.create.return_value = mock_response

    # Setup mock tracer
    mock_tracer = MagicMock()
    mock_tracer_class.return_value = mock_tracer

    # Setup mock CRUD functions
    mock_get_ancestor_id_from_response.return_value = (
        "resp_ancestor1234567890abcdef1234567890"
    )
    mock_create_conversation.return_value = None

    # Get the Dalgo project ID
    dalgo_project = db.exec(select(Project).where(Project.name == "Dalgo")).first()
    if not dalgo_project:
        pytest.skip("Dalgo project not found in the database")

    request_data = {
        "assistant_id": "assistant_dalgo",
        "question": "What is Dalgo?",
        "callback_url": "http://example.com/callback",
    }

    response = client.post("/responses", json=request_data, headers=user_api_key_header)

    assert response.status_code == 200
    response_json = response.json()
    assert response_json["success"] is True
    assert response_json["data"]["status"] == "processing"
    assert response_json["data"]["message"] == "Response creation started"


@patch("app.api.routes.responses.OpenAI")
@patch("app.api.routes.responses.get_provider_credential")
@patch("app.api.routes.responses.get_assistant_by_id")
@patch("app.api.routes.responses.LangfuseTracer")
@patch("app.api.routes.responses.get_ancestor_id_from_response")
@patch("app.api.routes.responses.create_conversation")
@patch("app.api.routes.responses.get_conversation_by_ancestor_id")
def test_responses_endpoint_without_vector_store(
    mock_get_conversation_by_ancestor_id,
    mock_create_conversation,
    mock_get_ancestor_id_from_response,
    mock_tracer_class,
    mock_get_assistant,
    mock_get_credential,
    mock_openai,
    db,
    user_api_key_header,
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
    mock_assistant.max_num_results = 20
    mock_get_assistant.return_value = mock_assistant

    # Setup mock OpenAI client
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # Setup the mock response object with proper response ID format
    mock_response = MagicMock()
    mock_response.id = "resp_1234567890abcdef1234567890abcdef1234567890"
    mock_response.output_text = "Test output"
    mock_response.model = "gpt-4"
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_response.usage.total_tokens = 15
    mock_response.output = []
    mock_response.previous_response_id = None
    mock_client.responses.create.return_value = mock_response

    # Setup mock tracer
    mock_tracer = MagicMock()
    mock_tracer_class.return_value = mock_tracer

    # Setup mock CRUD functions
    mock_get_ancestor_id_from_response.return_value = (
        "resp_ancestor1234567890abcdef1234567890"
    )
    mock_create_conversation.return_value = None

    # Get the Glific project ID
    glific_project = db.exec(select(Project).where(Project.name == "Glific")).first()
    if not glific_project:
        pytest.skip("Glific project not found in the database")

    request_data = {
        "assistant_id": "assistant_123",
        "question": "What is Glific?",
        "callback_url": "http://example.com/callback",
    }

    response = client.post("/responses", json=request_data, headers=user_api_key_header)
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


@patch("app.api.routes.responses.get_assistant_by_id")
def test_responses_endpoint_assistant_not_found(
    mock_get_assistant,
    db,
    user_api_key_header,
):
    """Test the /responses endpoint when assistant is not found."""
    # Setup mock assistant to return None (not found)
    mock_get_assistant.return_value = None

    request_data = {
        "assistant_id": "nonexistent_assistant",
        "question": "What is this?",
        "callback_url": "http://example.com/callback",
    }

    response = client.post("/responses", json=request_data, headers=user_api_key_header)
    assert response.status_code == 404
    response_json = response.json()
    assert response_json["detail"] == "Assistant not found or not active"


@patch("app.api.routes.responses.get_provider_credential")
@patch("app.api.routes.responses.get_assistant_by_id")
def test_responses_endpoint_no_openai_credentials(
    mock_get_assistant,
    mock_get_credential,
    db,
    user_api_key_header,
):
    """Test the /responses endpoint when OpenAI credentials are not configured."""
    # Setup mock assistant
    mock_assistant = MagicMock()
    mock_assistant.model = "gpt-4"
    mock_assistant.instructions = "Test instructions"
    mock_assistant.temperature = 0.1
    mock_assistant.vector_store_ids = []
    mock_get_assistant.return_value = mock_assistant

    # Setup mock credentials to return None (no credentials)
    mock_get_credential.return_value = None

    request_data = {
        "assistant_id": "assistant_123",
        "question": "What is this?",
        "callback_url": "http://example.com/callback",
    }

    response = client.post("/responses", json=request_data, headers=user_api_key_header)
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["success"] is False
    assert "OpenAI API key not configured" in response_json["error"]


@patch("app.api.routes.responses.get_provider_credential")
@patch("app.api.routes.responses.get_assistant_by_id")
def test_responses_endpoint_missing_api_key_in_credentials(
    mock_get_assistant,
    mock_get_credential,
    db,
    user_api_key_header,
):
    """Test the /responses endpoint when credentials exist but don't have api_key."""
    # Setup mock assistant
    mock_assistant = MagicMock()
    mock_assistant.model = "gpt-4"
    mock_assistant.instructions = "Test instructions"
    mock_assistant.temperature = 0.1
    mock_assistant.vector_store_ids = []
    mock_get_assistant.return_value = mock_assistant

    # Setup mock credentials without api_key
    mock_get_credential.return_value = {"other_key": "value"}

    request_data = {
        "assistant_id": "assistant_123",
        "question": "What is this?",
        "callback_url": "http://example.com/callback",
    }

    response = client.post("/responses", json=request_data, headers=user_api_key_header)
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["success"] is False
    assert "OpenAI API key not configured" in response_json["error"]


@patch("app.api.routes.responses.OpenAI")
@patch("app.api.routes.responses.get_provider_credential")
@patch("app.api.routes.responses.get_assistant_by_id")
@patch("app.api.routes.responses.LangfuseTracer")
@patch("app.api.routes.responses.get_ancestor_id_from_response")
@patch("app.api.routes.responses.create_conversation")
@patch("app.api.routes.responses.get_conversation_by_ancestor_id")
def test_responses_endpoint_with_file_search_results(
    mock_get_conversation_by_ancestor_id,
    mock_create_conversation,
    mock_get_ancestor_id_from_response,
    mock_tracer_class,
    mock_get_assistant,
    mock_get_credential,
    mock_openai,
    db,
    user_api_key_header,
):
    """Test the /responses endpoint with file search results in the response."""
    # Setup mock credentials
    mock_get_credential.return_value = {"api_key": "test_api_key"}

    # Setup mock assistant with vector store
    mock_assistant = MagicMock()
    mock_assistant.model = "gpt-4o"
    mock_assistant.instructions = "Test instructions"
    mock_assistant.temperature = 0.1
    mock_assistant.vector_store_ids = ["vs_test"]
    mock_assistant.max_num_results = 20
    mock_get_assistant.return_value = mock_assistant

    # Setup mock OpenAI client
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # Setup mock file search results
    mock_hit1 = MagicMock()
    mock_hit1.score = 0.95
    mock_hit1.text = "First search result"

    mock_hit2 = MagicMock()
    mock_hit2.score = 0.85
    mock_hit2.text = "Second search result"

    mock_file_search_call = MagicMock()
    mock_file_search_call.type = "file_search_call"
    mock_file_search_call.results = [mock_hit1, mock_hit2]

    # Setup the mock response object with file search results and proper response ID format
    mock_response = MagicMock()
    mock_response.id = "resp_1234567890abcdef1234567890abcdef1234567890"
    mock_response.output_text = "Test output with search results"
    mock_response.model = "gpt-4o"
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_response.usage.total_tokens = 15
    mock_response.output = [mock_file_search_call]
    mock_response.previous_response_id = None
    mock_client.responses.create.return_value = mock_response

    # Setup mock tracer
    mock_tracer = MagicMock()
    mock_tracer_class.return_value = mock_tracer

    # Setup mock CRUD functions
    mock_get_ancestor_id_from_response.return_value = (
        "resp_ancestor1234567890abcdef1234567890"
    )
    mock_create_conversation.return_value = None

    # Get the Dalgo project ID
    dalgo_project = db.exec(select(Project).where(Project.name == "Dalgo")).first()
    if not dalgo_project:
        pytest.skip("Dalgo project not found in the database")

    request_data = {
        "assistant_id": "assistant_dalgo",
        "question": "What is Dalgo?",
        "callback_url": "http://example.com/callback",
    }

    response = client.post("/responses", json=request_data, headers=user_api_key_header)

    assert response.status_code == 200
    response_json = response.json()
    assert response_json["success"] is True
    assert response_json["data"]["status"] == "processing"
    assert response_json["data"]["message"] == "Response creation started"

    # Verify OpenAI client was called with tools
    mock_client.responses.create.assert_called_once()
    call_args = mock_client.responses.create.call_args[1]
    assert "tools" in call_args
    assert call_args["tools"][0]["type"] == "file_search"
    assert call_args["tools"][0]["vector_store_ids"] == ["vs_test"]
    assert "include" in call_args
    assert "file_search_call.results" in call_args["include"]


@patch("app.api.routes.responses.OpenAI")
@patch("app.api.routes.responses.get_provider_credential")
@patch("app.api.routes.responses.get_assistant_by_id")
@patch("app.api.routes.responses.LangfuseTracer")
@patch("app.api.routes.responses.get_ancestor_id_from_response")
@patch("app.api.routes.responses.create_conversation")
@patch("app.api.routes.responses.get_conversation_by_ancestor_id")
def test_responses_endpoint_with_ancestor_conversation_found(
    mock_get_conversation_by_ancestor_id,
    mock_create_conversation,
    mock_get_ancestor_id_from_response,
    mock_tracer_class,
    mock_get_assistant,
    mock_get_credential,
    mock_openai,
    db,
    user_api_key_header: dict[str, str],
):
    """Test the /responses endpoint when a conversation is found by ancestor ID."""
    # Setup mock credentials
    mock_get_credential.return_value = {"api_key": "test_api_key"}

    # Setup mock assistant
    mock_assistant = MagicMock()
    mock_assistant.model = "gpt-4o"
    mock_assistant.instructions = "Test instructions"
    mock_assistant.temperature = 0.1
    mock_assistant.vector_store_ids = ["vs_test"]
    mock_assistant.max_num_results = 20
    mock_get_assistant.return_value = mock_assistant

    # Setup mock OpenAI client
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # Setup the mock response object
    mock_response = MagicMock()
    mock_response.id = "resp_1234567890abcdef1234567890abcdef1234567890"
    mock_response.output_text = "Test output"
    mock_response.model = "gpt-4o"
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_response.usage.total_tokens = 15
    mock_response.output = []
    mock_response.previous_response_id = "resp_ancestor1234567890abcdef1234567890"
    mock_client.responses.create.return_value = mock_response

    # Setup mock tracer
    mock_tracer = MagicMock()
    mock_tracer_class.return_value = mock_tracer

    # Setup mock CRUD functions
    mock_get_ancestor_id_from_response.return_value = (
        "resp_ancestor1234567890abcdef1234567890"
    )
    mock_create_conversation.return_value = None

    # Setup mock conversation found by ancestor ID
    mock_conversation = MagicMock()
    mock_conversation.response_id = "resp_latest1234567890abcdef1234567890"
    mock_conversation.ancestor_response_id = "resp_ancestor1234567890abcdef1234567890"
    mock_get_conversation_by_ancestor_id.return_value = mock_conversation

    # Get the Dalgo project ID
    dalgo_project = db.exec(select(Project).where(Project.name == "Dalgo")).first()
    if not dalgo_project:
        pytest.skip("Dalgo project not found in the database")

    request_data = {
        "assistant_id": "assistant_dalgo",
        "question": "What is Dalgo?",
        "callback_url": "http://example.com/callback",
        "response_id": "resp_ancestor1234567890abcdef1234567890",
    }

    response = client.post("/responses", json=request_data, headers=user_api_key_header)

    assert response.status_code == 200
    response_json = response.json()
    assert response_json["success"] is True
    assert response_json["data"]["status"] == "processing"
    assert response_json["data"]["message"] == "Response creation started"

    # Verify get_conversation_by_ancestor_id was called with correct parameters
    mock_get_conversation_by_ancestor_id.assert_called_once()
    call_args = mock_get_conversation_by_ancestor_id.call_args
    assert (
        call_args[1]["ancestor_response_id"]
        == "resp_ancestor1234567890abcdef1234567890"
    )
    assert call_args[1]["project_id"] == dalgo_project.id

    # Verify OpenAI client was called with the conversation's response_id as previous_response_id
    mock_client.responses.create.assert_called_once()
    call_args = mock_client.responses.create.call_args[1]
    assert call_args["previous_response_id"] == "resp_latest1234567890abcdef1234567890"


@patch("app.api.routes.responses.OpenAI")
@patch("app.api.routes.responses.get_provider_credential")
@patch("app.api.routes.responses.get_assistant_by_id")
@patch("app.api.routes.responses.LangfuseTracer")
@patch("app.api.routes.responses.get_ancestor_id_from_response")
@patch("app.api.routes.responses.create_conversation")
@patch("app.api.routes.responses.get_conversation_by_ancestor_id")
def test_responses_endpoint_with_ancestor_conversation_not_found(
    mock_get_conversation_by_ancestor_id,
    mock_create_conversation,
    mock_get_ancestor_id_from_response,
    mock_tracer_class,
    mock_get_assistant,
    mock_get_credential,
    mock_openai,
    db,
    user_api_key_header: dict[str, str],
):
    """Test the /responses endpoint when no conversation is found by ancestor ID."""
    # Setup mock credentials
    mock_get_credential.return_value = {"api_key": "test_api_key"}

    # Setup mock assistant
    mock_assistant = MagicMock()
    mock_assistant.model = "gpt-4o"
    mock_assistant.instructions = "Test instructions"
    mock_assistant.temperature = 0.1
    mock_assistant.vector_store_ids = ["vs_test"]
    mock_assistant.max_num_results = 20
    mock_get_assistant.return_value = mock_assistant

    # Setup mock OpenAI client
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # Setup the mock response object
    mock_response = MagicMock()
    mock_response.id = "resp_1234567890abcdef1234567890abcdef1234567890"
    mock_response.output_text = "Test output"
    mock_response.model = "gpt-4o"
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_response.usage.total_tokens = 15
    mock_response.output = []
    mock_response.previous_response_id = "resp_ancestor1234567890abcdef1234567890"
    mock_client.responses.create.return_value = mock_response

    # Setup mock tracer
    mock_tracer = MagicMock()
    mock_tracer_class.return_value = mock_tracer

    # Setup mock CRUD functions
    mock_get_ancestor_id_from_response.return_value = (
        "resp_ancestor1234567890abcdef1234567890"
    )
    mock_create_conversation.return_value = None

    # Setup mock conversation not found by ancestor ID
    mock_get_conversation_by_ancestor_id.return_value = None

    # Get the Dalgo project ID
    dalgo_project = db.exec(select(Project).where(Project.name == "Dalgo")).first()
    if not dalgo_project:
        pytest.skip("Dalgo project not found in the database")

    request_data = {
        "assistant_id": "assistant_dalgo",
        "question": "What is Dalgo?",
        "callback_url": "http://example.com/callback",
        "response_id": "resp_ancestor1234567890abcdef1234567890",
    }

    response = client.post("/responses", json=request_data, headers=user_api_key_header)

    assert response.status_code == 200
    response_json = response.json()
    assert response_json["success"] is True
    assert response_json["data"]["status"] == "processing"
    assert response_json["data"]["message"] == "Response creation started"

    # Verify get_conversation_by_ancestor_id was called with correct parameters
    mock_get_conversation_by_ancestor_id.assert_called_once()
    call_args = mock_get_conversation_by_ancestor_id.call_args
    assert (
        call_args[1]["ancestor_response_id"]
        == "resp_ancestor1234567890abcdef1234567890"
    )
    assert call_args[1]["project_id"] == dalgo_project.id

    # Verify OpenAI client was called with the original response_id as previous_response_id
    mock_client.responses.create.assert_called_once()
    call_args = mock_client.responses.create.call_args[1]
    assert (
        call_args["previous_response_id"] == "resp_ancestor1234567890abcdef1234567890"
    )


@patch("app.api.routes.responses.OpenAI")
@patch("app.api.routes.responses.get_provider_credential")
@patch("app.api.routes.responses.get_assistant_by_id")
@patch("app.api.routes.responses.LangfuseTracer")
@patch("app.api.routes.responses.get_ancestor_id_from_response")
@patch("app.api.routes.responses.create_conversation")
@patch("app.api.routes.responses.get_conversation_by_ancestor_id")
def test_responses_endpoint_without_response_id(
    mock_get_conversation_by_ancestor_id,
    mock_create_conversation,
    mock_get_ancestor_id_from_response,
    mock_tracer_class,
    mock_get_assistant,
    mock_get_credential,
    mock_openai,
    db,
    user_api_key_header: dict[str, str],
):
    """Test the /responses endpoint when no response_id is provided."""
    # Setup mock credentials
    mock_get_credential.return_value = {"api_key": "test_api_key"}

    # Setup mock assistant
    mock_assistant = MagicMock()
    mock_assistant.model = "gpt-4o"
    mock_assistant.instructions = "Test instructions"
    mock_assistant.temperature = 0.1
    mock_assistant.vector_store_ids = ["vs_test"]
    mock_assistant.max_num_results = 20
    mock_get_assistant.return_value = mock_assistant

    # Setup mock OpenAI client
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # Setup the mock response object
    mock_response = MagicMock()
    mock_response.id = "resp_1234567890abcdef1234567890abcdef1234567890"
    mock_response.output_text = "Test output"
    mock_response.model = "gpt-4o"
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_response.usage.total_tokens = 15
    mock_response.output = []
    mock_response.previous_response_id = None
    mock_client.responses.create.return_value = mock_response

    # Setup mock tracer
    mock_tracer = MagicMock()
    mock_tracer_class.return_value = mock_tracer

    # Setup mock CRUD functions
    mock_get_ancestor_id_from_response.return_value = (
        "resp_1234567890abcdef1234567890abcdef1234567890"
    )
    mock_create_conversation.return_value = None

    # Get the Dalgo project ID
    dalgo_project = db.exec(select(Project).where(Project.name == "Dalgo")).first()
    if not dalgo_project:
        pytest.skip("Dalgo project not found in the database")

    request_data = {
        "assistant_id": "assistant_dalgo",
        "question": "What is Dalgo?",
        "callback_url": "http://example.com/callback",
        # No response_id provided
    }

    response = client.post("/responses", json=request_data, headers=user_api_key_header)

    assert response.status_code == 200
    response_json = response.json()
    assert response_json["success"] is True
    assert response_json["data"]["status"] == "processing"
    assert response_json["data"]["message"] == "Response creation started"

    # Verify get_conversation_by_ancestor_id was not called since response_id is None
    mock_get_conversation_by_ancestor_id.assert_not_called()

    # Verify OpenAI client was called with None as previous_response_id
    mock_client.responses.create.assert_called_once()
    call_args = mock_client.responses.create.call_args[1]
    assert call_args["previous_response_id"] is None
