import openai
import pytest

from fastapi import BackgroundTasks, FastAPI
from fastapi.testclient import TestClient
from openai import OpenAIError
from sqlmodel import select
from unittest.mock import MagicMock, patch

from app.api.routes.threads import (
    handle_openai_error,
    poll_run_and_prepare_response,
    process_message_content,
    process_run,
    router,
    setup_thread,
    validate_thread,
)
from app.core.langfuse.langfuse import LangfuseTracer
from app.crud import get_thread_result
from app.models import OpenAI_Thread

# Create a minimal test app
app = FastAPI()
app.include_router(router)


# Override background tasks dependency to prevent real background tasks
def mock_background_tasks():
    return MagicMock(add_task=lambda *args, **kwargs: None)


app.dependency_overrides[BackgroundTasks] = mock_background_tasks

client = TestClient(app)


# Fast unit tests for utility functions (these run quickly)
def test_validate_thread_no_thread_id():
    """Test validate_thread when no thread_id is provided."""
    mock_client = MagicMock()
    is_valid, error = validate_thread(mock_client, None)
    assert is_valid is True
    assert error is None


def test_validate_thread_invalid_thread():
    """Test validate_thread with an invalid thread_id."""
    mock_client = MagicMock()
    error = openai.OpenAIError()
    error.message = "Invalid thread"
    error.response = MagicMock(status_code=404)
    error.body = {"message": "Invalid thread"}
    mock_client.beta.threads.runs.list.side_effect = error

    is_valid, error = validate_thread(mock_client, "invalid_thread")
    assert is_valid is False
    assert "Invalid thread ID" in error


def test_validate_thread_with_active_run():
    """Test validate_thread when there is an active run."""
    mock_client = MagicMock()
    mock_run = MagicMock()
    mock_run.status = "in_progress"
    mock_client.beta.threads.runs.list.return_value = MagicMock(data=[mock_run])

    is_valid, error = validate_thread(mock_client, "thread_123")
    assert is_valid is False
    assert "active run" in error.lower()
    assert "in_progress" in error


def test_validate_thread_with_queued_run():
    """Test validate_thread when there is a queued run."""
    mock_client = MagicMock()
    mock_run = MagicMock()
    mock_run.status = "queued"
    mock_client.beta.threads.runs.list.return_value = MagicMock(data=[mock_run])

    is_valid, error = validate_thread(mock_client, "thread_123")
    assert is_valid is False
    assert "active run" in error.lower()
    assert "queued" in error


def test_validate_thread_with_requires_action_run():
    """Test validate_thread when there is a run requiring action."""
    mock_client = MagicMock()
    mock_run = MagicMock()
    mock_run.status = "requires_action"
    mock_client.beta.threads.runs.list.return_value = MagicMock(data=[mock_run])

    is_valid, error = validate_thread(mock_client, "thread_123")
    assert is_valid is False
    assert "active run" in error.lower()
    assert "requires_action" in error


def test_validate_thread_with_completed_run():
    """Test validate_thread when there is a completed run."""
    mock_client = MagicMock()
    mock_run = MagicMock()
    mock_run.status = "completed"
    mock_client.beta.threads.runs.list.return_value = MagicMock(data=[mock_run])

    is_valid, error = validate_thread(mock_client, "thread_123")
    assert is_valid is True
    assert error is None


def test_validate_thread_with_no_runs():
    """Test validate_thread when there are no runs."""
    mock_client = MagicMock()
    mock_client.beta.threads.runs.list.return_value = MagicMock(data=[])

    is_valid, error = validate_thread(mock_client, "thread_123")
    assert is_valid is True
    assert error is None


def test_setup_thread_new_thread():
    """Test setup_thread for creating a new thread."""
    mock_client = MagicMock()
    mock_thread = MagicMock()
    mock_thread.id = "new_thread_id"
    mock_client.beta.threads.create.return_value = mock_thread
    mock_client.beta.threads.messages.create.return_value = None

    request = {"question": "Test question"}
    is_success, error = setup_thread(mock_client, request)

    assert is_success is True
    assert error is None
    assert request["thread_id"] == "new_thread_id"


def test_setup_thread_existing_thread():
    """Test setup_thread for using an existing thread."""
    mock_client = MagicMock()
    mock_client.beta.threads.messages.create.return_value = None

    request = {"question": "Test question", "thread_id": "existing_thread"}
    is_success, error = setup_thread(mock_client, request)

    assert is_success is True
    assert error is None


def test_process_message_content():
    """Test process_message_content with and without citation removal."""
    message = "Test message【1:2†citation】"

    # Test with citation removal
    processed = process_message_content(message, True)
    assert processed == "Test message"

    # Test without citation removal
    processed = process_message_content(message, False)
    assert processed == message


def test_handle_openai_error():
    """Test handle_openai_error with different error types."""
    # Test with error containing message in body
    error = MagicMock()
    error.body = {"message": "Test error message"}
    assert handle_openai_error(error) == "Test error message"

    # Test with error without message in body
    error = MagicMock()
    error.body = {}
    error.__str__.return_value = "Generic error"
    assert handle_openai_error(error) == "Generic error"


def test_handle_openai_error_with_message():
    """Test handle_openai_error when error has a message in its body."""
    error = MagicMock()
    error.body = {"message": "Test error message"}
    result = handle_openai_error(error)
    assert result == "Test error message"


def test_handle_openai_error_without_message():
    """Test handle_openai_error when error doesn't have a message in its body."""
    error = MagicMock()
    error.body = {"some_other_field": "value"}
    error.__str__.return_value = "Generic error message"
    result = handle_openai_error(error)
    assert result == "Generic error message"


def test_handle_openai_error_with_empty_body():
    """Test handle_openai_error when error has an empty body."""
    error = MagicMock()
    error.body = {}
    error.__str__.return_value = "Empty body error"
    result = handle_openai_error(error)
    assert result == "Empty body error"


def test_handle_openai_error_with_non_dict_body():
    """Test handle_openai_error when error body is not a dictionary."""
    error = MagicMock()
    error.body = "Not a dictionary"
    error.__str__.return_value = "Non-dict body error"
    result = handle_openai_error(error)
    assert result == "Non-dict body error"


def test_handle_openai_error_with_none_body():
    """Test handle_openai_error when error body is None."""
    error = MagicMock()
    error.body = None
    error.__str__.return_value = "None body error"
    result = handle_openai_error(error)
    assert result == "None body error"


@patch("app.api.routes.threads.OpenAI")
def test_poll_run_and_prepare_response_completed(mock_openai, db):
    mock_client = MagicMock()
    mock_run = MagicMock()
    mock_run.status = "completed"
    mock_client.beta.threads.runs.create_and_poll.return_value = mock_run

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=MagicMock(value="Answer"))]
    mock_client.beta.threads.messages.list.return_value.data = [mock_message]
    mock_openai.return_value = mock_client

    request = {
        "question": "What is Glific?",
        "assistant_id": "assist_123",
        "thread_id": "test_thread_001",
        "remove_citation": True,
    }

    poll_run_and_prepare_response(request, mock_client, db)

    result = get_thread_result(db, "test_thread_001")
    assert result.response.strip() == "Answer"


@patch("app.api.routes.threads.OpenAI")
def test_poll_run_and_prepare_response_openai_error_handling(mock_openai, db):
    mock_client = MagicMock()
    mock_error = OpenAIError("Simulated OpenAI error")
    mock_client.beta.threads.runs.create_and_poll.side_effect = mock_error
    mock_openai.return_value = mock_client

    request = {
        "question": "Failing run",
        "assistant_id": "assist_123",
        "thread_id": "test_openai_error",
    }

    poll_run_and_prepare_response(request, mock_client, db)

    # Since thread_id is not the primary key, use select query
    statement = select(OpenAI_Thread).where(
        OpenAI_Thread.thread_id == "test_openai_error"
    )
    result = db.exec(statement).first()

    assert result is not None
    assert result.response is None
    assert result.status == "failed"
    assert "Simulated OpenAI error" in (result.error or "")


@patch("app.api.routes.threads.OpenAI")
def test_poll_run_and_prepare_response_non_completed(mock_openai, db):
    mock_client = MagicMock()
    mock_run = MagicMock(status="failed")
    mock_client.beta.threads.runs.create_and_poll.return_value = mock_run
    mock_openai.return_value = mock_client

    request = {
        "question": "Incomplete run",
        "assistant_id": "assist_123",
        "thread_id": "test_non_complete",
    }

    poll_run_and_prepare_response(request, mock_client, db)

    # thread_id is not the primary key, so we query using SELECT
    statement = select(OpenAI_Thread).where(
        OpenAI_Thread.thread_id == "test_non_complete"
    )
    result = db.exec(statement).first()

    assert result is not None
    assert result.response is None
    assert result.status == "failed"


@patch("app.api.routes.threads.OpenAI")
@pytest.mark.parametrize(
    "remove_citation, expected_message",
    [
        (
            True,
            "Glific is an open-source, two-way messaging platform designed for "
            "nonprofits to scale their outreach via WhatsApp",
        ),
        (
            False,
            "Glific is an open-source, two-way messaging platform designed for "
            "nonprofits to scale their outreach via WhatsApp【1:2†citation】",
        ),
    ],
)
def test_process_run_variants(mock_openai, remove_citation, expected_message):
    """
    Test process_run for both remove_citation variants:
    - Mocks the OpenAI client to simulate a completed run.
    - Verifies that send_callback is called with the expected message based on
      the remove_citation flag.
    """
    # Setup the mock client.
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # Create the request with the variable remove_citation flag.
    request = {
        "question": "What is Glific?",
        "assistant_id": "assistant_123",
        "callback_url": "http://example.com/callback",
        "thread_id": "thread_123",
        "remove_citation": remove_citation,
    }

    # Simulate a completed run.
    mock_run = MagicMock()
    mock_run.status = "completed"
    mock_client.beta.threads.runs.create_and_poll.return_value = mock_run

    # Set up the dummy message based on the remove_citation flag.
    base_message = (
        "Glific is an open-source, two-way messaging platform designed for "
        "nonprofits to scale their outreach via WhatsApp"
    )
    citation_message = (
        base_message if remove_citation else f"{base_message}【1:2†citation】"
    )
    dummy_message = MagicMock()
    dummy_message.content = [MagicMock(text=MagicMock(value=citation_message))]
    mock_client.beta.threads.messages.list.return_value.data = [dummy_message]

    tracer = LangfuseTracer()
    # Patch send_callback and invoke process_run.
    with patch("app.api.routes.threads.send_callback") as mock_send_callback:
        process_run(request, mock_client, tracer)
        mock_send_callback.assert_called_once()
        callback_url, payload = mock_send_callback.call_args[0]
        assert callback_url == request["callback_url"]
        assert payload["data"]["message"] == expected_message
        assert payload["data"]["status"] == "success"
        assert payload["data"]["thread_id"] == "thread_123"
        assert payload["success"] is True
