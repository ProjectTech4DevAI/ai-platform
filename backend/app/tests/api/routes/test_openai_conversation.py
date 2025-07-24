import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.openai_conversation import OpenAIConversationCreate
from app.crud.openai_conversation import create_openai_conversation
from app.tests.utils.utils import get_project


def test_get_conversation_by_id(
    client: TestClient, db: Session, normal_user_api_key_headers: dict[str, str]
):
    """Test getting a conversation by ID."""
    project = get_project(db)
    # Create a conversation first
    conversation_data = OpenAIConversationCreate(
        response_id="resp_test688080a1c52c819c937",
        ancestor_response_id="ancestor_456",
        user_question="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        assistant_id="asst_testXLnzQYrQlAEzrOA",
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
    assert data["data"]["response_id"] == "resp_test688080a1c52c819c937"
    assert data["data"]["is_deleted"] is False
    assert data["data"]["deleted_at"] is None


def test_get_conversation_by_response_id(
    client: TestClient, db: Session, normal_user_api_key_headers: dict[str, str]
):
    """Test getting a conversation by response_id."""
    project = get_project(db)
    # Create a conversation first
    conversation_data = OpenAIConversationCreate(
        response_id="resp_test688080a1c52c819c937",
        ancestor_response_id="ancestor_456",
        user_question="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        assistant_id="asst_testXLnzQYrQlAEzrOA",
        project_id=project.id,
        organization_id=project.organization_id,
    )
    create_openai_conversation(db, conversation_data)
    response = client.get(
        "/api/v1/openai-conversation/response/resp_test688080a1c52c819c937",
        headers=normal_user_api_key_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["response_id"] == "resp_test688080a1c52c819c937"
    assert data["data"]["is_deleted"] is False
    assert data["data"]["deleted_at"] is None


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
        assistant_id="asst_testXLnzQYrQlAEzrOA",
        project_id=project.id,
        organization_id=project.organization_id,
    )
    conversation_data2 = OpenAIConversationCreate(
        response_id="resp_2",
        ancestor_response_id="ancestor_123",
        user_question="What is the capital of Spain?",
        response="The capital of Spain is Madrid.",
        model="gpt-4o",
        assistant_id="asst_testXLnzQYrQlAEzrOA",
        project_id=project.id,
        organization_id=project.organization_id,
    )
    conversation_data3 = OpenAIConversationCreate(
        response_id="resp_3",
        ancestor_response_id="ancestor_456",
        user_question="What is the capital of Italy?",
        response="The capital of Italy is Rome.",
        model="gpt-4o",
        assistant_id="asst_testXLnzQYrQlAEzrOA",
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
    for conv in data["data"]:
        assert conv["is_deleted"] is False
        assert conv["deleted_at"] is None


def test_delete_conversation_by_id(
    client: TestClient, db: Session, normal_user_api_key_headers: dict[str, str]
):
    """Test deleting a conversation by ID."""
    from app.crud.openai_conversation import get_openai_conversation_by_id

    project = get_project(db)
    # Create a conversation first
    conversation_data = OpenAIConversationCreate(
        response_id="resp_test688080a1c52c819c937",
        user_question="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        assistant_id="asst_testXLnzQYrQlAEzrOA",
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
    # Fetch from DB and check is_deleted and deleted_at
    deleted_conv = get_openai_conversation_by_id(db, conversation.id)
    assert deleted_conv.is_deleted is True
    assert deleted_conv.deleted_at is not None


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
        assistant_id="asst_testXLnzQYrQlAEzrOA",
        project_id=project.id,
        organization_id=project.organization_id,
    )
    conversation_data2 = OpenAIConversationCreate(
        response_id="resp_2",
        ancestor_response_id="ancestor_2",
        user_question="What is the capital of Spain?",
        response="The capital of Spain is Madrid.",
        model="gpt-4o",
        assistant_id="asst_testXLnzQYrQlAEzrOA",
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
    for conv in data["data"]:
        assert conv["is_deleted"] is False
        assert conv["deleted_at"] is None
