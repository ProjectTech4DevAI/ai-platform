import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.crud.openai_conversation import create_openai_conversation
from app.models.openai_conversation import OpenAIConversationCreate
from app.models import APIKeyPublic


def test_get_conversation_by_id(
    client: TestClient, db: Session, user_api_key: APIKeyPublic
):
    """Test getting a conversation by ID."""
    # Create a conversation first
    conversation_data = OpenAIConversationCreate(
        response_id="resp_test688080a1c52c819c937",
        ancestor_response_id="ancestor_456",
        user_question="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        assistant_id="asst_testXLnzQYrQlAEzrOA",
        project_id=user_api_key.project_id,
        organization_id=user_api_key.organization_id,
    )
    conversation = create_openai_conversation(db, conversation_data)
    response = client.get(
        f"/api/v1/openai-conversation/{conversation.id}",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == conversation.id
    assert data["data"]["response_id"] == "resp_test688080a1c52c819c937"
    assert data["data"]["is_deleted"] is False
    assert data["data"]["deleted_at"] is None


def test_get_conversation_by_response_id(
    client: TestClient, db: Session, user_api_key: APIKeyPublic
):
    """Test getting a conversation by response_id."""
    # Create a conversation first
    conversation_data = OpenAIConversationCreate(
        response_id="resp_test688080a1c52c819c937",
        ancestor_response_id="ancestor_456",
        user_question="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        assistant_id="asst_testXLnzQYrQlAEzrOA",
        project_id=user_api_key.project_id,
        organization_id=user_api_key.organization_id,
    )
    create_openai_conversation(db, conversation_data)
    response = client.get(
        "/api/v1/openai-conversation/response/resp_test688080a1c52c819c937",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["response_id"] == "resp_test688080a1c52c819c937"
    assert data["data"]["is_deleted"] is False
    assert data["data"]["deleted_at"] is None


def test_get_conversations_by_ancestor(
    client: TestClient, db: Session, user_api_key: APIKeyPublic
):
    """Test getting conversations by ancestor_response_id."""
    # Create multiple conversations with same ancestor
    conversation_data1 = OpenAIConversationCreate(
        response_id="resp_test688080a1c52c819c937",
        ancestor_response_id="resp_test688080a1c52c819c937",
        user_question="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        assistant_id="asst_testXLnzQYrQlAEzrOA",
        project_id=user_api_key.project_id,
        organization_id=user_api_key.organization_id,
    )
    conversation_data2 = OpenAIConversationCreate(
        response_id="resp_test688080a1c52c819c937_2",
        ancestor_response_id="resp_test688080a1c52c819c937",
        user_question="What is the capital of Spain?",
        response="The capital of Spain is Madrid.",
        model="gpt-4o",
        assistant_id="asst_testXLnzQYrQlAEzrOA",
        project_id=user_api_key.project_id,
        organization_id=user_api_key.organization_id,
    )
    conversation_data3 = OpenAIConversationCreate(
        response_id="resp_test688080a1c52c819c937_3",
        ancestor_response_id="resp_test688080a1c52c819c937",
        user_question="What is the capital of Italy?",
        response="The capital of Italy is Rome.",
        model="gpt-4o",
        assistant_id="asst_testXLnzQYrQlAEzrOA",
        project_id=user_api_key.project_id,
        organization_id=user_api_key.organization_id,
    )

    conv_1 = create_openai_conversation(db, conversation_data1)
    conv_2 = create_openai_conversation(db, conversation_data2)
    conv_3 = create_openai_conversation(db, conversation_data3)

    print(conv_1)
    print(conv_2)
    print(conv_3)
    response = client.get(
        "/api/v1/openai-conversation/ancestor/ancestor_123",
        headers={"X-API-KEY": user_api_key.key},
    )
    print(response.json())

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) == 2
    assert all(conv["ancestor_response_id"] == "ancestor_123" for conv in data["data"])
    for conv in data["data"]:
        assert conv["is_deleted"] is False
        assert conv["deleted_at"] is None


def test_delete_conversation_by_id(
    client: TestClient, db: Session, user_api_key: APIKeyPublic
):
    """Test deleting a conversation by ID."""
    from app.crud.openai_conversation import get_openai_conversation_by_id

    # Create a conversation first
    conversation_data = OpenAIConversationCreate(
        response_id="resp_test688080a1c52c819c937",
        user_question="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        assistant_id="asst_testXLnzQYrQlAEzrOA",
        project_id=user_api_key.project_id,
        organization_id=user_api_key.organization_id,
    )
    conversation = create_openai_conversation(db, conversation_data)
    response = client.delete(
        f"/api/v1/openai-conversation/{conversation.id}",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "deleted successfully" in data["data"]["message"]
    # Fetch from DB and check is_deleted and deleted_at
    deleted_conv = get_openai_conversation_by_id(db, conversation.id)
    assert deleted_conv.is_deleted is True
    assert deleted_conv.deleted_at is not None


def test_list_conversations(
    client: TestClient, db: Session, user_api_key: APIKeyPublic
):
    """Test listing all conversations."""
    # Create multiple conversations
    conversation_data1 = OpenAIConversationCreate(
        response_id="resp_test688080a1c52c819c937",
        ancestor_response_id="ancestor_1",
        user_question="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        assistant_id="asst_testXLnzQYrQlAEzrOA",
        project_id=user_api_key.project_id,
        organization_id=user_api_key.organization_id,
    )
    conversation_data2 = OpenAIConversationCreate(
        response_id="resp_test688080a1c52c819c937_2",
        ancestor_response_id="ancestor_2",
        user_question="What is the capital of Spain?",
        response="The capital of Spain is Madrid.",
        model="gpt-4o",
        assistant_id="asst_testXLnzQYrQlAEzrOA",
        project_id=user_api_key.project_id,
        organization_id=user_api_key.organization_id,
    )
    conversation1 = create_openai_conversation(db, conversation_data1)
    conversation2 = create_openai_conversation(db, conversation_data2)
    response = client.get(
        "/api/v1/openai-conversation/list",
        headers={"X-API-KEY": user_api_key.key},
        params={"skip": 0, "limit": 100},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    # Should contain at least the two conversations we just created
    response_ids = [conv["response_id"] for conv in data["data"]]
    assert conversation1.response_id in response_ids
    assert conversation2.response_id in response_ids
    for conv in data["data"]:
        assert conv["is_deleted"] is False
        assert conv["deleted_at"] is None
