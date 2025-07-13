import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from unittest.mock import MagicMock, patch
from app.main import app
from app.tests.utils.utils import random_email
from app.core.security import get_password_hash
from app.tests.utils.openai import mock_openai_assistant

client = TestClient(app)


@pytest.fixture
def normal_user_api_key_header():
    return {"X-API-KEY":"ApiKey Px8y47B6roJHin1lWLkR88eiDrFdXSJRZmFQazzai8j9"}


@patch("app.api.routes.assistant.fetch_assistant_from_openai")
def test_ingest_assistant_success(
    mock_fetch_assistant,
    db: Session,
    normal_user_api_key_header: str,
):
    """Test successful assistant ingestion from OpenAI."""

    # Setup mock return value

    mock_assistant = mock_openai_assistant()

    mock_fetch_assistant.return_value = mock_assistant

    response = client.post(
        f"/api/v1/assistant/{mock_assistant.id}/ingest",
        headers=normal_user_api_key_header,
    )

    assert response.status_code == 201
    response_json = response.json()
    assert response_json["success"] is True
    assert response_json["data"]["assistant_id"] == mock_assistant.id
    

@patch("app.api.routes.assistant.configure_openai")
def test_ingest_assistant_openai_not_configured(
    mock_configure_openai,
    db: Session,
    normal_user_api_key_header: dict,
):
    """Test assistant ingestion failure when OpenAI is not configured."""
    
    # Setup mock to return failure for OpenAI configuration
    mock_configure_openai.return_value = (None, False)
    
    # Use a mock assistant ID
    mock_assistant_id = "asst_123456789"
    
    response = client.post(
        f"/api/v1/assistant/{mock_assistant_id}/ingest",
        headers=normal_user_api_key_header,
    )
    
    assert response.status_code == 400
    response_json = response.json()
    assert response_json["success"] is False
    assert response_json["error"] == "OpenAI not configured for this organization."
