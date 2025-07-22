import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.openai_conversation import OpenAIConversationCreate
from app.crud.openai_conversation import create_openai_conversation
from app.tests.utils.utils import get_project


def test_create_conversation(
    client: TestClient, db: Session, normal_user_api_key_headers: dict[str, str]
):
    """Test creating a new conversation."""
    project = get_project(db)
    conversation_data = {
        "response_id": "resp_123",
        "ancestor_response_id": "ancestor_456",
        "previous_response_id": "prev_789",
        "user_question": "What is the capital of France?",
        "response": "The capital of France is Paris.",
        "model": "gpt-4o",
        "assistant_id": "asst_123",
        "project_id": project.id,
        "organization_id": project.organization_id,
    }
    response = client.post(
        "/api/v1/openai-conversation/create",
        json=conversation_data,
        headers=normal_user_api_key_headers,
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
    client: TestClient, db: Session, normal_user_api_key_headers: dict[str, str]
):
    """Test getting a conversation by ID."""
    project = get_project(db)
    # Create a conversation first
    conversation_data = OpenAIConversationCreate(
        response_id="resp_123",
        ancestor_response_id="ancestor_456",
        user_question="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        assistant_id="asst_123",
        project_id=project.id,
        organization_id=project.organization_id,
    )
    conversation = create_openai_conversation(db, conversation_data)
    response = client.get(
        f"/api/v1/openai-conversation/{conversation.id}",
        headers=normal_user_api_key_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == conversation.id
    assert data["data"]["response_id"] == "resp_123"


def test_get_conversation_by_response_id(
    client: TestClient, db: Session, normal_user_api_key_headers: dict[str, str]
):
    """Test getting a conversation by response_id."""
    project = get_project(db)
    # Create a conversation first
    conversation_data = OpenAIConversationCreate(
        response_id="resp_123",
        ancestor_response_id="ancestor_456",
        user_question="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        assistant_id="asst_123",
        project_id=project.id,
        organization_id=project.organization_id,
    )
    create_openai_conversation(db, conversation_data)
    response = client.get(
        "/api/v1/openai-conversation/response/resp_123",
        headers=normal_user_api_key_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["response_id"] == "resp_123"


def test_get_conversations_by_ancestor(
    client: TestClient, db: Session, normal_user_api_key_headers: dict[str, str]
):
    """Test getting conversations by ancestor_response_id."""
    project = get_project(db)
    # Create multiple conversations with same ancestor
    conversation_data1 = OpenAIConversationCreate(
        response_id="resp_1",
        ancestor_response_id="ancestor_123",
        user_question="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        assistant_id="asst_123",
        project_id=project.id,
        organization_id=project.organization_id,
    )
    conversation_data2 = OpenAIConversationCreate(
        response_id="resp_2",
        ancestor_response_id="ancestor_123",
        user_question="What is the capital of Spain?",
        response="The capital of Spain is Madrid.",
        model="gpt-4o",
        assistant_id="asst_123",
        project_id=project.id,
        organization_id=project.organization_id,
    )
    conversation_data3 = OpenAIConversationCreate(
        response_id="resp_3",
        ancestor_response_id="ancestor_456",
        user_question="What is the capital of Italy?",
        response="The capital of Italy is Rome.",
        model="gpt-4o",
        assistant_id="asst_123",
        project_id=project.id,
        organization_id=project.organization_id,
    )

    create_openai_conversation(db, conversation_data1)
    create_openai_conversation(db, conversation_data2)
    create_openai_conversation(db, conversation_data3)
    response = client.get(
        "/api/v1/openai-conversation/ancestor/ancestor_123",
        headers=normal_user_api_key_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) == 2
    assert all(conv["ancestor_response_id"] == "ancestor_123" for conv in data["data"])


def test_update_conversation(
    client: TestClient, db: Session, normal_user_api_key_headers: dict[str, str]
):
    """Test updating a conversation."""
    project = get_project(db)
    # Create a conversation first
    conversation_data = OpenAIConversationCreate(
        response_id="resp_123",
        ancestor_response_id="ancestor_456",
        user_question="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        assistant_id="asst_123",
        project_id=project.id,
        organization_id=project.organization_id,
    )
    conversation = create_openai_conversation(db, conversation_data)

    update_data = {
        "ancestor_response_id": "ancestor_789",
        "previous_response_id": "prev_123",
    }
    response = client.put(
        f"/api/v1/openai-conversation/{conversation.id}",
        json=update_data,
        headers=normal_user_api_key_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["ancestor_response_id"] == "ancestor_789"
    assert data["data"]["previous_response_id"] == "prev_123"
    assert data["data"]["response_id"] == "resp_123"  # Should remain unchanged


def test_delete_conversation_by_id(
    client: TestClient, db: Session, normal_user_api_key_headers: dict[str, str]
):
    """Test deleting a conversation by ID."""
    project = get_project(db)
    # Create a conversation first
    conversation_data = OpenAIConversationCreate(
        response_id="resp_123",
        user_question="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        assistant_id="asst_123",
        project_id=project.id,
        organization_id=project.organization_id,
    )
    conversation = create_openai_conversation(db, conversation_data)
    response = client.delete(
        f"/api/v1/openai-conversation/{conversation.id}",
        headers=normal_user_api_key_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "deleted successfully" in data["data"]["message"]


def test_list_conversations(
    client: TestClient, db: Session, normal_user_api_key_headers: dict[str, str]
):
    """Test listing all conversations."""
    project = get_project(db)
    # Create multiple conversations
    conversation_data1 = OpenAIConversationCreate(
        response_id="resp_1",
        ancestor_response_id="ancestor_1",
        user_question="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        assistant_id="asst_123",
        project_id=project.id,
        organization_id=project.organization_id,
    )
    conversation_data2 = OpenAIConversationCreate(
        response_id="resp_2",
        ancestor_response_id="ancestor_2",
        user_question="What is the capital of Spain?",
        response="The capital of Spain is Madrid.",
        model="gpt-4o",
        assistant_id="asst_123",
        project_id=project.id,
        organization_id=project.organization_id,
    )
    conversation1 = create_openai_conversation(db, conversation_data1)
    conversation2 = create_openai_conversation(db, conversation_data2)
    response = client.get(
        "/api/v1/openai-conversation/list",
        headers=normal_user_api_key_headers,
        params={"skip": 0, "limit": 100},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    # Should contain at least the two conversations we just created
    response_ids = [conv["response_id"] for conv in data["data"]]
    assert conversation1.response_id in response_ids
    assert conversation2.response_id in response_ids
