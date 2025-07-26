import pytest
from uuid import uuid4
from sqlmodel import Session
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.tests.utils.conversation import get_conversation


@pytest.fixture
def conversation_create_payload():
    return {
        "response_id": f"resp_{uuid4()}",
        "ancestor_response_id": None,
        "previous_response_id": None,
        "user_question": "What is the capital of France?",
        "response": "The capital of France is Paris.",
        "model": "gpt-4o",
        "assistant_id": f"asst_{uuid4()}",
    }


@pytest.fixture
def conversation_update_payload():
    return {
        "response": "The capital of France is Paris, which is a beautiful city.",
        "model": "gpt-4o-mini",
    }


def test_create_conversation_success(
    client: TestClient,
    conversation_create_payload: dict,
    user_api_key_header: dict,
):
    """Test successful conversation creation."""
    response = client.post(
        "/api/v1/openai-conversation",
        json=conversation_create_payload,
        headers=user_api_key_header,
    )

    assert response.status_code == 201
    response_data = response.json()
    assert response_data["success"] is True
    assert (
        response_data["data"]["response_id"]
        == conversation_create_payload["response_id"]
    )
    assert (
        response_data["data"]["user_question"]
        == conversation_create_payload["user_question"]
    )
    assert response_data["data"]["response"] == conversation_create_payload["response"]
    assert response_data["data"]["model"] == conversation_create_payload["model"]
    assert (
        response_data["data"]["assistant_id"]
        == conversation_create_payload["assistant_id"]
    )


def test_create_conversation_invalid_data(
    client: TestClient,
    user_api_key_header: dict,
):
    """Test conversation creation with invalid data."""
    invalid_payload = {
        "response_id": "",  # Empty response_id
        "user_question": "",  # Empty user_question
        "model": "",  # Empty model
        "assistant_id": "",  # Empty assistant_id
    }

    response = client.post(
        "/api/v1/openai-conversation",
        json=invalid_payload,
        headers=user_api_key_header,
    )

    assert response.status_code == 422


def test_upsert_conversation_success(
    client: TestClient,
    conversation_create_payload: dict,
    user_api_key_header: dict,
):
    """Test successful conversation upsert."""
    response = client.post(
        "/api/v1/openai-conversation/upsert",
        json=conversation_create_payload,
        headers=user_api_key_header,
    )

    assert response.status_code == 201
    response_data = response.json()
    assert response_data["success"] is True
    assert (
        response_data["data"]["response_id"]
        == conversation_create_payload["response_id"]
    )


def test_upsert_conversation_update_existing(
    client: TestClient,
    conversation_create_payload: dict,
    user_api_key_header: dict,
):
    """Test upsert conversation updates existing conversation."""
    # First create a conversation
    response1 = client.post(
        "/api/v1/openai-conversation/upsert",
        json=conversation_create_payload,
        headers=user_api_key_header,
    )
    assert response1.status_code == 201

    # Update the payload and upsert again
    conversation_create_payload["response"] = "Updated response"
    response2 = client.post(
        "/api/v1/openai-conversation/upsert",
        json=conversation_create_payload,
        headers=user_api_key_header,
    )

    assert response2.status_code == 201
    response_data = response2.json()
    assert response_data["success"] is True
    assert response_data["data"]["response"] == "Updated response"


def test_update_conversation_success(
    client: TestClient,
    db: Session,
    conversation_update_payload: dict,
    user_api_key_header: dict,
):
    """Test successful conversation update."""
    # Get the project ID from the user's API key
    from app.tests.utils.utils import get_user_from_api_key

    api_key = get_user_from_api_key(db, user_api_key_header)

    # Create a conversation in the same project as the API key
    conversation = get_conversation(db, project_id=api_key.project_id)
    conversation_id = conversation.id

    response = client.patch(
        f"/api/v1/openai-conversation/{conversation_id}",
        json=conversation_update_payload,
        headers=user_api_key_header,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["data"]["response"] == conversation_update_payload["response"]
    assert response_data["data"]["model"] == conversation_update_payload["model"]


def test_update_conversation_not_found(
    client: TestClient,
    conversation_update_payload: dict,
    user_api_key_header: dict,
):
    """Test conversation update with non-existent ID."""
    response = client.patch(
        "/api/v1/openai-conversation/99999",
        json=conversation_update_payload,
        headers=user_api_key_header,
    )

    assert response.status_code == 404
    response_data = response.json()
    assert "not found" in response_data["error"]


def test_get_conversation_success(
    client: TestClient,
    db: Session,
    user_api_key_header: dict,
):
    """Test successful conversation retrieval by ID."""
    # Get the project ID from the user's API key
    from app.tests.utils.utils import get_user_from_api_key

    api_key = get_user_from_api_key(db, user_api_key_header)

    # Create a conversation in the same project as the API key
    conversation = get_conversation(db, project_id=api_key.project_id)
    conversation_id = conversation.id

    response = client.get(
        f"/api/v1/openai-conversation/{conversation_id}",
        headers=user_api_key_header,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["data"]["id"] == conversation_id
    assert response_data["data"]["response_id"] == conversation.response_id


def test_get_conversation_not_found(
    client: TestClient,
    user_api_key_header: dict,
):
    """Test conversation retrieval with non-existent ID."""
    response = client.get(
        "/api/v1/openai-conversation/99999",
        headers=user_api_key_header,
    )

    assert response.status_code == 404
    response_data = response.json()
    assert "not found" in response_data["error"]


def test_get_conversation_by_response_id_success(
    client: TestClient,
    db: Session,
    user_api_key_header: dict,
):
    """Test successful conversation retrieval by response ID."""
    # Get the project ID from the user's API key
    from app.tests.utils.utils import get_user_from_api_key

    api_key = get_user_from_api_key(db, user_api_key_header)

    # Create a conversation in the same project as the API key
    conversation = get_conversation(db, project_id=api_key.project_id)
    response_id = conversation.response_id

    response = client.get(
        f"/api/v1/openai-conversation/response/{response_id}",
        headers=user_api_key_header,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["data"]["response_id"] == response_id


def test_get_conversation_by_response_id_not_found(
    client: TestClient,
    user_api_key_header: dict,
):
    """Test conversation retrieval with non-existent response ID."""
    response = client.get(
        "/api/v1/openai-conversation/response/non_existent_response_id",
        headers=user_api_key_header,
    )

    assert response.status_code == 404
    response_data = response.json()
    assert "not found" in response_data["error"]


def test_get_conversation_thread_success(
    client: TestClient,
    db: Session,
    user_api_key_header: dict,
):
    """Test successful conversation thread retrieval."""
    conversation = get_conversation(db)
    response_id = conversation.response_id

    response = client.get(
        f"/api/v1/openai-conversation/thread/{response_id}",
        headers=user_api_key_header,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert isinstance(response_data["data"], list)


def test_list_conversations_success(
    client: TestClient,
    db: Session,
    user_api_key_header: dict,
):
    """Test successful conversation listing."""
    # Get the project ID from the user's API key
    from app.tests.utils.utils import get_user_from_api_key

    api_key = get_user_from_api_key(db, user_api_key_header)

    # Create a conversation in the same project as the API key
    get_conversation(db, project_id=api_key.project_id)

    response = client.get(
        "/api/v1/openai-conversation",
        headers=user_api_key_header,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert isinstance(response_data["data"], list)
    assert len(response_data["data"]) > 0


def test_list_conversations_with_pagination(
    client: TestClient,
    db: Session,
    user_api_key_header: dict,
):
    """Test conversation listing with pagination."""
    # Create multiple conversations
    for _ in range(3):
        get_conversation(db)

    response = client.get(
        "/api/v1/openai-conversation?skip=1&limit=2",
        headers=user_api_key_header,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert isinstance(response_data["data"], list)
    assert len(response_data["data"]) <= 2


def test_list_conversations_invalid_pagination(
    client: TestClient,
    user_api_key_header: dict,
):
    """Test conversation listing with invalid pagination parameters."""
    response = client.get(
        "/api/v1/openai-conversation?skip=-1&limit=0",
        headers=user_api_key_header,
    )

    assert response.status_code == 422


def test_list_conversations_by_assistant_success(
    client: TestClient,
    db: Session,
    user_api_key_header: dict,
):
    """Test successful conversation listing by assistant."""
    conversation = get_conversation(db)
    assistant_id = conversation.assistant_id

    response = client.get(
        f"/api/v1/openai-conversation/assistant/{assistant_id}",
        headers=user_api_key_header,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert isinstance(response_data["data"], list)
    # All returned conversations should have the same assistant_id
    for conv in response_data["data"]:
        assert conv["assistant_id"] == assistant_id


def test_delete_conversation_success(
    client: TestClient,
    db: Session,
    user_api_key_header: dict,
):
    """Test successful conversation deletion."""
    # Get the project ID from the user's API key
    from app.tests.utils.utils import get_user_from_api_key

    api_key = get_user_from_api_key(db, user_api_key_header)

    # Create a conversation in the same project as the API key
    conversation = get_conversation(db, project_id=api_key.project_id)
    conversation_id = conversation.id

    response = client.delete(
        f"/api/v1/openai-conversation/{conversation_id}",
        headers=user_api_key_header,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert "deleted successfully" in response_data["data"]["message"]


def test_delete_conversation_not_found(
    client: TestClient,
    user_api_key_header: dict,
):
    """Test conversation deletion with non-existent ID."""
    response = client.delete(
        "/api/v1/openai-conversation/99999",
        headers=user_api_key_header,
    )

    assert response.status_code == 404
    response_data = response.json()
    assert "not found" in response_data["error"]
