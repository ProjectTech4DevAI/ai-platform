import pytest
from unittest.mock import MagicMock

from openai import OpenAIError
from sqlmodel import Session

from app.core.langfuse.langfuse import LangfuseTracer
from app.models import Assistant, ResponsesAPIRequest
from app.services.response.response import generate_response


@pytest.fixture
def assistant_mock() -> Assistant:
    """Fixture to create an assistant in DB with id=123."""
    assistant = Assistant(
        id="123",
        name="Test Assistant",
        model="gpt-4",
        temperature=0.7,
        instructions="You are a helpful assistant.",
        vector_store_ids=["vs1", "vs2"],
        max_num_results=5,
    )
    return assistant


def test_generate_response_success(db: Session, assistant_mock: Assistant):
    """Test successful OpenAI response generation."""
    mock_response = MagicMock()

    mock_client = MagicMock()

    request = ResponsesAPIRequest(
        assistant_id="123",
        question="What is the capital of France?",
        callback_url="http://example.com/callback",
    )

    response, error = generate_response(
        tracer=LangfuseTracer(),
        client=mock_client,
        assistant=assistant_mock,
        request=request,
        ancestor_id=None,
    )

    mock_client.responses.create.assert_called_once()
    assert error is None


def test_generate_response_openai_error(assistant_mock: Assistant):
    """Test OpenAI error handling path."""

    mock_client = MagicMock()
    mock_client.responses.create.side_effect = OpenAIError("API failed")

    request = ResponsesAPIRequest(
        assistant_id="123",
        question="What is the capital of Germany?",
    )

    response, error = generate_response(
        tracer=LangfuseTracer(),
        client=mock_client,
        assistant=assistant_mock,
        request=request,
        ancestor_id=None,
    )

    assert response is None
    assert error is not None
    assert "API failed" in error
