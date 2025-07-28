import pytest
import secrets
import string
from sqlmodel import Session
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.tests.utils.conversation import get_conversation


def generate_realistic_id(prefix: str, length: int = 40) -> str:
    """Generate a realistic ID similar to OpenAI's format (alphanumeric only)"""
    chars = string.ascii_lowercase + string.digits
    random_part = "".join(secrets.choice(chars) for _ in range(length))
    return f"{prefix}{random_part}"


def test_get_conversation_success(
    client: TestClient,
    db: Session,
    user_api_key_header: dict,
):
    """Test successful conversation retrieval."""
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
    assert response_data["data"]["id"] == conversation.id


def test_get_conversation_by_response_id_not_found(
    client: TestClient,
    user_api_key_header: dict,
):
    """Test conversation retrieval with non-existent response ID."""
    response = client.get(
        "/api/v1/openai-conversation/response/nonexistent_response_id",
        headers=user_api_key_header,
    )

    assert response.status_code == 404
    response_data = response.json()
    assert "not found" in response_data["error"]


def test_get_conversation_by_ancestor_id_success(
    client: TestClient,
    db: Session,
    user_api_key_header: dict,
):
    """Test successful conversation retrieval by ancestor ID."""
    # Get the project ID from the user's API key
    from app.tests.utils.utils import get_user_from_api_key
    from app.crud.openai_conversation import create_conversation
    from app.models import OpenAIConversationCreate

    api_key = get_user_from_api_key(db, user_api_key_header)

    # Create a conversation with an ancestor in the same project as the API key
    ancestor_response_id = generate_realistic_id("resp_", 40)
    conversation_data = OpenAIConversationCreate(
        response_id=generate_realistic_id("resp_", 40),
        ancestor_response_id=ancestor_response_id,
        previous_response_id=None,
        user_question="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        assistant_id=generate_realistic_id("asst_", 20),
    )

    conversation = create_conversation(
        session=db,
        conversation=conversation_data,
        project_id=api_key.project_id,
        organization_id=api_key.organization_id,
    )

    response = client.get(
        f"/api/v1/openai-conversation/ancestor/{ancestor_response_id}",
        headers=user_api_key_header,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["data"]["ancestor_response_id"] == ancestor_response_id
    assert response_data["data"]["id"] == conversation.id


def test_get_conversation_by_ancestor_id_not_found(
    client: TestClient,
    user_api_key_header: dict,
):
    """Test conversation retrieval with non-existent ancestor ID."""
    response = client.get(
        "/api/v1/openai-conversation/ancestor/nonexistent_ancestor_id",
        headers=user_api_key_header,
    )

    assert response.status_code == 404
    response_data = response.json()
    assert "not found" in response_data["error"]


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

    # Verify the conversation is marked as deleted
    response = client.get(
        f"/api/v1/openai-conversation/{conversation_id}",
        headers=user_api_key_header,
    )
    assert response.status_code == 404


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
