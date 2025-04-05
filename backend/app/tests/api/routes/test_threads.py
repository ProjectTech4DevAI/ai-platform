from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.routes.threads import process_run, router
from app.models import APIKey

# Wrap the router in a FastAPI app instance.
app = FastAPI()
app.include_router(router)
client = TestClient(app)


@patch("app.api.routes.threads.OpenAI")
def test_threads_endpoint(mock_openai, db):
    """
    Test the /threads endpoint when creating a new thread.
    The patched OpenAI client simulates:
    - A successful assistant ID validation.
    - New thread creation with a dummy thread id.
    - No existing runs.
    The expected response should have status "processing" and include a thread_id.
    """
    # Create a dummy client to simulate OpenAI API behavior.
    dummy_client = MagicMock()
    # Simulate a valid assistant ID by ensuring retrieve doesn't raise an error.
    dummy_client.beta.assistants.retrieve.return_value = None
    # Simulate thread creation.
    dummy_thread = MagicMock()
    dummy_thread.id = "dummy_thread_id"
    dummy_client.beta.threads.create.return_value = dummy_thread
    # Simulate message creation.
    dummy_client.beta.threads.messages.create.return_value = None
    # Simulate that no active run exists.
    dummy_client.beta.threads.runs.list.return_value = MagicMock(data=[])

    mock_openai.return_value = dummy_client

    # Get an API key from the database
    api_key_record = db.exec(select(APIKey).where(APIKey.is_deleted is False)).first()
    if not api_key_record:
        pytest.skip("No API key found in the database for testing")

    headers = {"X-API-KEY": api_key_record.key}

    request_data = {
        "question": "What is Glific?",
        "assistant_id": "assistant_123",
        "callback_url": "http://example.com/callback",
    }
    response = client.post("/threads", json=request_data, headers=headers)
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["success"] is True
    assert response_json["data"]["status"] == "processing"
    assert response_json["data"]["message"] == "Run started"
    assert response_json["data"]["thread_id"] == "dummy_thread_id"


@patch("app.api.routes.threads.OpenAI")
@pytest.mark.parametrize(
    "remove_citation, expected_message",
    [
        (
            True,
            "Glific is an open-source, two-way messaging platform designed for nonprofits to scale their outreach via WhatsApp",
        ),
        (
            False,
            "Glific is an open-source, two-way messaging platform designed for nonprofits to scale their outreach via WhatsApp【1:2†citation】",
        ),
    ],
)
def test_process_run_variants(mock_openai, remove_citation, expected_message):
    """
    Test process_run for both remove_citation variants:
    - Mocks the OpenAI client to simulate a completed run.
    - Verifies that send_callback is called with the expected message based on the remove_citation flag.
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
    base_message = "Glific is an open-source, two-way messaging platform designed for nonprofits to scale their outreach via WhatsApp"
    citation_message = (
        base_message if remove_citation else f"{base_message}【1:2†citation】"
    )
    dummy_message = MagicMock()
    dummy_message.content = [MagicMock(text=MagicMock(value=citation_message))]
    mock_client.beta.threads.messages.list.return_value.data = [dummy_message]

    # Patch send_callback and invoke process_run.
    with patch("app.api.routes.threads.send_callback") as mock_send_callback:
        process_run(request, mock_client)
        mock_send_callback.assert_called_once()
        callback_url, payload = mock_send_callback.call_args[0]
        assert callback_url == request["callback_url"]
        assert payload["data"]["message"] == expected_message
        assert payload["data"]["status"] == "success"
        assert payload["data"]["thread_id"] == "thread_123"
        assert payload["success"] is True
