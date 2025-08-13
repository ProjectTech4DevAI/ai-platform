from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.routes.responses import router, process_response


# Wrap the router in a FastAPI app instance
app = FastAPI()
app.include_router(router)
client = TestClient(app)


def create_mock_assistant(model="gpt-4o", vector_store_ids=None, max_num_results=20):
    """Create a mock assistant with default or custom values."""
    if vector_store_ids is None:
        vector_store_ids = ["vs_test"]

    mock_assistant = MagicMock()
    mock_assistant.model = model
    mock_assistant.instructions = "Test instructions"
    mock_assistant.temperature = 0.1
    mock_assistant.vector_store_ids = vector_store_ids
    mock_assistant.max_num_results = max_num_results
    return mock_assistant


def create_mock_openai_response(
    response_id="resp_1234567890abcdef1234567890abcdef1234567890",
    output_text="Test output",
    model="gpt-4o",
    output=None,
    previous_response_id=None,
):
    """Create a mock OpenAI response with default or custom values."""
    if output is None:
        output = []

    mock_response = MagicMock()
    mock_response.id = response_id
    mock_response.output_text = output_text
    mock_response.model = model
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_response.usage.total_tokens = 15
    mock_response.output = output
    mock_response.previous_response_id = previous_response_id
    return mock_response


def create_mock_file_search_results():
    """Create mock file search results for testing."""
    mock_hit1 = MagicMock()
    mock_hit1.score = 0.95
    mock_hit1.text = "First search result"

    mock_hit2 = MagicMock()
    mock_hit2.score = 0.85
    mock_hit2.text = "Second search result"

    mock_file_search_call = MagicMock()
    mock_file_search_call.type = "file_search_call"
    mock_file_search_call.results = [mock_hit1, mock_hit2]

    return [mock_file_search_call]


def create_mock_conversation(
    response_id="resp_latest1234567890abcdef1234567890",
    ancestor_response_id="resp_ancestor1234567890abcdef1234567890",
):
    """Create a mock conversation with default or custom values."""
    mock_conversation = MagicMock()
    mock_conversation.response_id = response_id
    mock_conversation.ancestor_response_id = ancestor_response_id
    return mock_conversation


def setup_common_mocks(
    mock_get_credential,
    mock_get_assistant,
    mock_openai,
    mock_tracer_class,
    mock_get_ancestor_id_from_response,
    mock_create_conversation,
    mock_get_conversation_by_ancestor_id,
    assistant_model="gpt-4o",
    vector_store_ids=None,
    conversation_found=True,
    response_output=None,
):
    """Setup common mocks used across multiple tests."""
    # Setup mock credentials
    mock_get_credential.return_value = {"api_key": "test_api_key"}

    # Setup mock assistant
    mock_assistant = create_mock_assistant(assistant_model, vector_store_ids)
    mock_get_assistant.return_value = mock_assistant

    # Setup mock OpenAI client
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # Setup mock response
    mock_response = create_mock_openai_response(output=response_output)
    mock_client.responses.create.return_value = mock_response

    # Setup mock tracer
    mock_tracer = MagicMock()
    mock_tracer_class.return_value = mock_tracer

    # Setup mock CRUD functions
    mock_get_ancestor_id_from_response.return_value = (
        "resp_ancestor1234567890abcdef1234567890"
    )
    mock_create_conversation.return_value = None

    # Setup mock conversation if needed
    if conversation_found:
        mock_conversation = create_mock_conversation()
        mock_get_conversation_by_ancestor_id.return_value = mock_conversation
    else:
        mock_get_conversation_by_ancestor_id.return_value = None

    return mock_client, mock_assistant


@patch("app.api.routes.responses.process_response")
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
    mock_process_response,
    db,
    user_api_key_header: dict[str, str],
    user_api_key,
):
    """Test the /responses endpoint for successful response creation."""

    # Mock the background task to prevent actual execution
    mock_process_response.return_value = None

    # Setup common mocks
    mock_client, mock_assistant = setup_common_mocks(
        mock_get_credential,
        mock_get_assistant,
        mock_openai,
        mock_tracer_class,
        mock_get_ancestor_id_from_response,
        mock_create_conversation,
        mock_get_conversation_by_ancestor_id,
    )

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

    # Verify that the background task was scheduled with correct parameters
    mock_process_response.assert_called_once()
    call_args = mock_process_response.call_args
    assert call_args[0][0].assistant_id == "assistant_dalgo"
    assert call_args[0][0].question == "What is Dalgo?"
    assert call_args[0][0].callback_url == "http://example.com/callback"
    assert call_args[0][0].response_id is None


@patch("app.api.routes.responses.process_response")
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
    mock_process_response,
    db,
    user_api_key_header,
    user_api_key,
):
    """Test the /responses endpoint when assistant has no vector store configured."""
    # Mock the background task to prevent actual execution
    mock_process_response.return_value = None

    # Setup common mocks with no vector store
    mock_client, mock_assistant = setup_common_mocks(
        mock_get_credential,
        mock_get_assistant,
        mock_openai,
        mock_tracer_class,
        mock_get_ancestor_id_from_response,
        mock_create_conversation,
        mock_get_conversation_by_ancestor_id,
        assistant_model="gpt-4",
        vector_store_ids=[],
    )

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

    # Verify that the background task was scheduled with correct parameters
    mock_process_response.assert_called_once()
    call_args = mock_process_response.call_args
    assert call_args[0][0].assistant_id == "assistant_123"
    assert call_args[0][0].question == "What is Glific?"
    assert call_args[0][0].callback_url == "http://example.com/callback"
    assert call_args[0][0].response_id is None


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
    mock_assistant = create_mock_assistant()
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
    mock_assistant = create_mock_assistant()
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


@patch("app.api.routes.responses.process_response")
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
    mock_process_response,
    db,
    user_api_key_header,
    user_api_key,
):
    """Test the /responses endpoint with file search results in the response."""
    # Mock the background task to prevent actual execution
    mock_process_response.return_value = None

    # Setup common mocks with file search results
    mock_client, mock_assistant = setup_common_mocks(
        mock_get_credential,
        mock_get_assistant,
        mock_openai,
        mock_tracer_class,
        mock_get_ancestor_id_from_response,
        mock_create_conversation,
        mock_get_conversation_by_ancestor_id,
        response_output=create_mock_file_search_results(),
    )

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

    # Verify that the background task was scheduled with correct parameters
    mock_process_response.assert_called_once()
    call_args = mock_process_response.call_args
    assert call_args[0][0].assistant_id == "assistant_dalgo"
    assert call_args[0][0].question == "What is Dalgo?"
    assert call_args[0][0].callback_url == "http://example.com/callback"
    assert call_args[0][0].response_id is None


@patch("app.api.routes.responses.process_response")
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
    mock_process_response,
    db,
    user_api_key_header: dict[str, str],
    user_api_key,
):
    """Test the /responses endpoint when a conversation is found by ancestor ID."""
    # Mock the background task to prevent actual execution
    mock_process_response.return_value = None

    # Setup common mocks with conversation found
    mock_client, mock_assistant = setup_common_mocks(
        mock_get_credential,
        mock_get_assistant,
        mock_openai,
        mock_tracer_class,
        mock_get_ancestor_id_from_response,
        mock_create_conversation,
        mock_get_conversation_by_ancestor_id,
        conversation_found=True,
    )

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

    # Verify that the background task was scheduled with correct parameters
    mock_process_response.assert_called_once()
    call_args = mock_process_response.call_args
    assert call_args[0][0].assistant_id == "assistant_dalgo"
    assert call_args[0][0].question == "What is Dalgo?"
    assert call_args[0][0].callback_url == "http://example.com/callback"
    assert call_args[0][0].response_id == "resp_ancestor1234567890abcdef1234567890"


@patch("app.api.routes.responses.process_response")
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
    mock_process_response,
    db,
    user_api_key_header: dict[str, str],
    user_api_key,
):
    """Test the /responses endpoint when no conversation is found by ancestor ID."""
    # Mock the background task to prevent actual execution
    mock_process_response.return_value = None

    # Setup common mocks with conversation not found
    mock_client, mock_assistant = setup_common_mocks(
        mock_get_credential,
        mock_get_assistant,
        mock_openai,
        mock_tracer_class,
        mock_get_ancestor_id_from_response,
        mock_create_conversation,
        mock_get_conversation_by_ancestor_id,
        conversation_found=False,
    )

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

    # Verify that the background task was scheduled with correct parameters
    mock_process_response.assert_called_once()
    call_args = mock_process_response.call_args
    assert call_args[0][0].assistant_id == "assistant_dalgo"
    assert call_args[0][0].question == "What is Dalgo?"
    assert call_args[0][0].callback_url == "http://example.com/callback"
    assert call_args[0][0].response_id == "resp_ancestor1234567890abcdef1234567890"


@patch("app.api.routes.responses.process_response")
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
    mock_process_response,
    db,
    user_api_key_header: dict[str, str],
    user_api_key,
):
    """Test the /responses endpoint when no response_id is provided."""
    # Mock the background task to prevent actual execution
    mock_process_response.return_value = None

    # Setup common mocks
    mock_client, mock_assistant = setup_common_mocks(
        mock_get_credential,
        mock_get_assistant,
        mock_openai,
        mock_tracer_class,
        mock_get_ancestor_id_from_response,
        mock_create_conversation,
        mock_get_conversation_by_ancestor_id,
    )

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

    # Verify that the background task was scheduled with correct parameters
    mock_process_response.assert_called_once()
    call_args = mock_process_response.call_args
    assert call_args[0][0].assistant_id == "assistant_dalgo"
    assert call_args[0][0].question == "What is Dalgo?"
    assert call_args[0][0].callback_url == "http://example.com/callback"
    assert call_args[0][0].response_id is None


@patch("app.api.routes.responses.get_conversation_by_ancestor_id")
@patch("app.api.routes.responses.create_conversation")
@patch("app.api.routes.responses.get_ancestor_id_from_response")
@patch("app.api.routes.responses.send_callback")
def test_process_response_ancestor_conversation_found(
    mock_send_callback,
    mock_get_ancestor_id_from_response,
    mock_create_conversation,
    mock_get_conversation_by_ancestor_id,
    db,
    user_api_key,
):
    """Test process_response function when ancestor conversation is found."""
    from app.api.routes.responses import ResponsesAPIRequest

    # Setup mock request
    request = ResponsesAPIRequest(
        assistant_id="assistant_dalgo",
        question="What is Dalgo?",
        callback_url="http://example.com/callback",
        response_id="resp_ancestor1234567890abcdef1234567890",
    )

    # Setup mock assistant
    mock_assistant = create_mock_assistant()

    # Setup mock OpenAI client
    mock_client = MagicMock()
    mock_response = create_mock_openai_response(
        response_id="resp_new1234567890abcdef1234567890abcdef",
        output_text="Test response",
        previous_response_id="resp_latest1234567890abcdef1234567890",
    )
    mock_client.responses.create.return_value = mock_response

    # Setup mock tracer
    mock_tracer = MagicMock()

    # Setup mock conversation found by ancestor ID
    mock_conversation = create_mock_conversation()
    mock_get_conversation_by_ancestor_id.return_value = mock_conversation

    # Setup mock CRUD functions
    mock_get_ancestor_id_from_response.return_value = (
        "resp_ancestor1234567890abcdef1234567890"
    )
    mock_create_conversation.return_value = None

    # Call process_response
    process_response(
        request=request,
        client=mock_client,
        assistant=mock_assistant,
        tracer=mock_tracer,
        project_id=user_api_key.project_id,
        organization_id=user_api_key.organization_id,
        session=db,
    )

    # Verify get_conversation_by_ancestor_id was called with correct parameters
    mock_get_conversation_by_ancestor_id.assert_called_once_with(
        session=db,
        ancestor_response_id="resp_ancestor1234567890abcdef1234567890",
        project_id=user_api_key.project_id,
    )

    # Verify OpenAI client was called with the conversation's response_id as
    # previous_response_id
    mock_client.responses.create.assert_called_once()
    call_args = mock_client.responses.create.call_args[1]
    assert call_args["previous_response_id"] == (
        "resp_latest1234567890abcdef1234567890"
    )

    # Verify create_conversation was called
    mock_create_conversation.assert_called_once()

    # Verify send_callback was called
    mock_send_callback.assert_called_once()


@patch("app.api.routes.responses.get_conversation_by_ancestor_id")
@patch("app.api.routes.responses.create_conversation")
@patch("app.api.routes.responses.get_ancestor_id_from_response")
@patch("app.api.routes.responses.send_callback")
def test_process_response_ancestor_conversation_not_found(
    mock_send_callback,
    mock_get_ancestor_id_from_response,
    mock_create_conversation,
    mock_get_conversation_by_ancestor_id,
    db,
    user_api_key,
):
    """Test process_response function when no ancestor conversation is found."""
    from app.api.routes.responses import ResponsesAPIRequest

    # Setup mock request
    request = ResponsesAPIRequest(
        assistant_id="assistant_dalgo",
        question="What is Dalgo?",
        callback_url="http://example.com/callback",
        response_id="resp_ancestor1234567890abcdef1234567890",
    )

    # Setup mock assistant
    mock_assistant = create_mock_assistant()

    # Setup mock OpenAI client
    mock_client = MagicMock()
    mock_response = create_mock_openai_response(
        response_id="resp_new1234567890abcdef1234567890abcdef",
        output_text="Test response",
        previous_response_id="resp_ancestor1234567890abcdef1234567890",
    )
    mock_client.responses.create.return_value = mock_response

    # Setup mock tracer
    mock_tracer = MagicMock()

    # Setup mock conversation not found by ancestor ID
    mock_get_conversation_by_ancestor_id.return_value = None

    # Setup mock CRUD functions
    mock_get_ancestor_id_from_response.return_value = (
        "resp_ancestor1234567890abcdef1234567890"
    )
    mock_create_conversation.return_value = None

    # Call process_response
    process_response(
        request=request,
        client=mock_client,
        assistant=mock_assistant,
        tracer=mock_tracer,
        project_id=user_api_key.project_id,
        organization_id=user_api_key.organization_id,
        session=db,
    )

    # Verify get_conversation_by_ancestor_id was called with correct parameters
    mock_get_conversation_by_ancestor_id.assert_called_once_with(
        session=db,
        ancestor_response_id="resp_ancestor1234567890abcdef1234567890",
        project_id=user_api_key.project_id,
    )

    # Verify OpenAI client was called with the original response_id as
    # previous_response_id
    mock_client.responses.create.assert_called_once()
    call_args = mock_client.responses.create.call_args[1]
    assert call_args["previous_response_id"] == (
        "resp_ancestor1234567890abcdef1234567890"
    )

    # Verify create_conversation was called
    mock_create_conversation.assert_called_once()

    # Verify send_callback was called
    mock_send_callback.assert_called_once()
