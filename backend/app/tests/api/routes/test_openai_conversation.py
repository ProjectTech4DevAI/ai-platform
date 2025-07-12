import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.openai_conversation import (
    OpenAIConversationCreate,
    OpenAIConversationUpdate,
)
from app.crud.openai_conversation import create_openai_conversation


def test_create_conversation(client: TestClient, superuser_token_headers: dict):
    """Test creating a new conversation."""
    conversation_data = {
        "response_id": "resp_123",
        "ancestor_response_id": "ancestor_456",
        "previous_response_id": "prev_789",
    }

    response = client.post(
        "/api/openai-conversation/create",
        json=conversation_data,
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["response_id"] == "resp_123"
    assert data["data"]["ancestor_response_id"] == "ancestor_456"
    assert data["data"]["previous_response_id"] == "prev_789"
    assert "id" in data["data"]
    assert "inserted_at" in data["data"]
    assert "updated_at" in data["data"]


def test_get_conversation_by_id(
    client: TestClient, superuser_token_headers: dict, db: Session
):
    """Test getting a conversation by ID."""
    # Create a conversation first
    conversation_data = OpenAIConversationCreate(
        response_id="resp_123", ancestor_response_id="ancestor_456"
    )
    conversation = create_openai_conversation(db, conversation_data)

    response = client.get(
        f"/api/openai-conversation/{conversation.id}", headers=superuser_token_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == conversation.id
    assert data["data"]["response_id"] == "resp_123"


def test_get_conversation_by_id_not_found(
    client: TestClient, superuser_token_headers: dict
):
    """Test getting a conversation by ID that doesn't exist."""
    response = client.get(
        "/api/openai-conversation/99999", headers=superuser_token_headers
    )

    assert response.status_code == 404
    data = response.json()
    assert "Conversation not found" in data["detail"]


def test_get_conversation_by_response_id(
    client: TestClient, superuser_token_headers: dict, db: Session
):
    """Test getting a conversation by response_id."""
    # Create a conversation first
    conversation_data = OpenAIConversationCreate(
        response_id="resp_123", ancestor_response_id="ancestor_456"
    )
    create_openai_conversation(db, conversation_data)

    response = client.get(
        "/api/openai-conversation/response/resp_123", headers=superuser_token_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["response_id"] == "resp_123"


def test_get_conversation_by_response_id_not_found(
    client: TestClient, superuser_token_headers: dict
):
    """Test getting a conversation by response_id that doesn't exist."""
    response = client.get(
        "/api/openai-conversation/response/nonexistent", headers=superuser_token_headers
    )

    assert response.status_code == 404
    data = response.json()
    assert "Conversation not found" in data["detail"]


def test_get_conversations_by_ancestor(
    client: TestClient, superuser_token_headers: dict, db: Session
):
    """Test getting conversations by ancestor_response_id."""
    # Create multiple conversations with same ancestor
    conversation_data1 = OpenAIConversationCreate(
        response_id="resp_1", ancestor_response_id="ancestor_123"
    )
    conversation_data2 = OpenAIConversationCreate(
        response_id="resp_2", ancestor_response_id="ancestor_123"
    )
    conversation_data3 = OpenAIConversationCreate(
        response_id="resp_3", ancestor_response_id="ancestor_456"
    )

    create_openai_conversation(db, conversation_data1)
    create_openai_conversation(db, conversation_data2)
    create_openai_conversation(db, conversation_data3)

    response = client.get(
        "/api/openai-conversation/ancestor/ancestor_123",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) == 2
    assert all(conv["ancestor_response_id"] == "ancestor_123" for conv in data["data"])


def test_list_conversations(
    client: TestClient, superuser_token_headers: dict, db: Session
):
    """Test listing all conversations with pagination."""
    # Create multiple conversations
    conversation_data1 = OpenAIConversationCreate(response_id="resp_1")
    conversation_data2 = OpenAIConversationCreate(response_id="resp_2")
    conversation_data3 = OpenAIConversationCreate(response_id="resp_3")

    create_openai_conversation(db, conversation_data1)
    create_openai_conversation(db, conversation_data2)
    create_openai_conversation(db, conversation_data3)

    response = client.get(
        "/api/openai-conversation/list?skip=0&limit=10", headers=superuser_token_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) >= 3  # Should have at least 3 conversations


def test_update_conversation(
    client: TestClient, superuser_token_headers: dict, db: Session
):
    """Test updating a conversation."""
    # Create a conversation first
    conversation_data = OpenAIConversationCreate(
        response_id="resp_123", ancestor_response_id="ancestor_456"
    )
    conversation = create_openai_conversation(db, conversation_data)

    update_data = {
        "ancestor_response_id": "ancestor_789",
        "previous_response_id": "prev_123",
    }

    response = client.put(
        f"/api/openai-conversation/{conversation.id}",
        json=update_data,
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["ancestor_response_id"] == "ancestor_789"
    assert data["data"]["previous_response_id"] == "prev_123"
    assert data["data"]["response_id"] == "resp_123"  # Should remain unchanged


def test_update_conversation_not_found(
    client: TestClient, superuser_token_headers: dict
):
    """Test updating a conversation that doesn't exist."""
    update_data = {"ancestor_response_id": "ancestor_789"}

    response = client.put(
        "/api/openai-conversation/99999",
        json=update_data,
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
    data = response.json()
    assert "Conversation not found" in data["detail"]


def test_delete_conversation_by_id(
    client: TestClient, superuser_token_headers: dict, db: Session
):
    """Test deleting a conversation by ID."""
    # Create a conversation first
    conversation_data = OpenAIConversationCreate(response_id="resp_123")
    conversation = create_openai_conversation(db, conversation_data)

    response = client.delete(
        f"/api/openai-conversation/{conversation.id}", headers=superuser_token_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "deleted successfully" in data["data"]["message"]


def test_delete_conversation_by_id_not_found(
    client: TestClient, superuser_token_headers: dict
):
    """Test deleting a conversation by ID that doesn't exist."""
    response = client.delete(
        "/api/openai-conversation/99999", headers=superuser_token_headers
    )

    assert response.status_code == 404
    data = response.json()
    assert "Conversation not found" in data["detail"]
