import secrets
import string
from sqlmodel import Session

from app.crud.openai_conversation import (
    get_conversation_by_id,
    get_conversation_by_response_id,
    get_conversation_by_ancestor_id,
    get_conversations_by_project,
    create_conversation,
    delete_conversation,
)
from app.models import OpenAIConversationCreate
from app.tests.utils.conversation import get_conversation
from app.tests.utils.utils import get_project, get_organization


def generate_openai_id(prefix: str, length: int = 40) -> str:
    """Generate a realistic ID similar to OpenAI's format (alphanumeric only)"""
    chars = string.ascii_lowercase + string.digits
    random_part = "".join(secrets.choice(chars) for _ in range(length))
    return f"{prefix}{random_part}"


def test_get_conversation_by_id_success(db: Session):
    """Test successful conversation retrieval by ID."""
    project = get_project(db)
    conversation = get_conversation(db, project_id=project.id)

    retrieved_conversation = get_conversation_by_id(
        session=db,
        conversation_id=conversation.id,
        project_id=project.id,
    )

    assert retrieved_conversation is not None
    assert retrieved_conversation.id == conversation.id
    assert retrieved_conversation.response_id == conversation.response_id


def test_get_conversation_by_id_not_found(db: Session):
    """Test conversation retrieval by non-existent ID."""
    project = get_project(db)

    retrieved_conversation = get_conversation_by_id(
        session=db,
        conversation_id=99999,
        project_id=project.id,
    )

    assert retrieved_conversation is None


def test_get_conversation_by_response_id_success(db: Session):
    """Test successful conversation retrieval by response ID."""
    project = get_project(db)
    conversation = get_conversation(db, project_id=project.id)

    retrieved_conversation = get_conversation_by_response_id(
        session=db,
        response_id=conversation.response_id,
        project_id=project.id,
    )

    assert retrieved_conversation is not None
    assert retrieved_conversation.id == conversation.id
    assert retrieved_conversation.response_id == conversation.response_id


def test_get_conversation_by_response_id_not_found(db: Session):
    """Test conversation retrieval by non-existent response ID."""
    project = get_project(db)

    retrieved_conversation = get_conversation_by_response_id(
        session=db,
        response_id="nonexistent_response_id",
        project_id=project.id,
    )

    assert retrieved_conversation is None


def test_get_conversation_by_ancestor_id_success(db: Session):
    """Test successful conversation retrieval by ancestor ID."""
    project = get_project(db)
    organization = get_organization(db)

    # Create a conversation with an ancestor
    ancestor_response_id = generate_openai_id("resp_", 40)
    conversation_data = OpenAIConversationCreate(
        response_id=generate_openai_id("resp_", 40),
        ancestor_response_id=ancestor_response_id,
        previous_response_id=None,
        user_question="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        assistant_id=generate_openai_id("asst_", 20),
    )

    conversation = create_conversation(
        session=db,
        conversation=conversation_data,
        project_id=project.id,
        organization_id=organization.id,
    )

    retrieved_conversation = get_conversation_by_ancestor_id(
        session=db,
        ancestor_response_id=ancestor_response_id,
        project_id=project.id,
    )

    assert retrieved_conversation is not None
    assert retrieved_conversation.id == conversation.id
    assert retrieved_conversation.ancestor_response_id == ancestor_response_id


def test_get_conversation_by_ancestor_id_not_found(db: Session):
    """Test conversation retrieval by non-existent ancestor ID."""
    project = get_project(db)

    retrieved_conversation = get_conversation_by_ancestor_id(
        session=db,
        ancestor_response_id="nonexistent_ancestor_id",
        project_id=project.id,
    )

    assert retrieved_conversation is None


def test_get_conversations_by_project_success(db: Session):
    """Test successful conversation listing by project."""
    project = get_project(db)
    organization = get_organization(db)

    # Create multiple conversations directly
    for i in range(3):
        conversation_data = OpenAIConversationCreate(
            response_id=generate_openai_id("resp_", 40),
            ancestor_response_id=None,
            previous_response_id=None,
            user_question=f"Test question {i}",
            response=f"Test response {i}",
            model="gpt-4o",
            assistant_id=generate_openai_id("asst_", 20),
        )
        create_conversation(
            session=db,
            conversation=conversation_data,
            project_id=project.id,
            organization_id=organization.id,
        )

    conversations = get_conversations_by_project(
        session=db,
        project_id=project.id,
    )

    assert len(conversations) >= 3
    for conversation in conversations:
        assert conversation.project_id == project.id
        assert conversation.is_deleted is False


def test_get_conversations_by_project_with_pagination(db: Session):
    """Test conversation listing by project with pagination."""
    project = get_project(db)

    # Create multiple conversations
    for _ in range(5):
        get_conversation(db, project_id=project.id)

    conversations = get_conversations_by_project(
        session=db,
        project_id=project.id,
        skip=1,
        limit=2,
    )

    assert len(conversations) <= 2


def test_delete_conversation_success(db: Session):
    """Test successful conversation deletion."""
    project = get_project(db)
    conversation = get_conversation(db, project_id=project.id)

    deleted_conversation = delete_conversation(
        session=db,
        conversation_id=conversation.id,
        project_id=project.id,
    )

    assert deleted_conversation is not None
    assert deleted_conversation.id == conversation.id
    assert deleted_conversation.is_deleted is True
    assert deleted_conversation.deleted_at is not None


def test_delete_conversation_not_found(db: Session):
    """Test conversation deletion with non-existent ID."""
    project = get_project(db)

    deleted_conversation = delete_conversation(
        session=db,
        conversation_id=99999,
        project_id=project.id,
    )

    assert deleted_conversation is None


def test_conversation_soft_delete_behavior(db: Session):
    """Test that deleted conversations are not returned by get functions."""
    project = get_project(db)
    conversation = get_conversation(db, project_id=project.id)

    # Delete the conversation
    delete_conversation(
        session=db,
        conversation_id=conversation.id,
        project_id=project.id,
    )

    # Verify it's not returned by get functions
    retrieved_conversation = get_conversation_by_id(
        session=db,
        conversation_id=conversation.id,
        project_id=project.id,
    )
    assert retrieved_conversation is None

    retrieved_conversation = get_conversation_by_response_id(
        session=db,
        response_id=conversation.response_id,
        project_id=project.id,
    )
    assert retrieved_conversation is None

    conversations = get_conversations_by_project(
        session=db,
        project_id=project.id,
    )
    assert conversation.id not in [c.id for c in conversations]
