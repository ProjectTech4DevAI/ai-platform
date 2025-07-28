import secrets
import string
import pytest
from sqlmodel import Session

from app.crud.openai_conversation import (
    get_conversation_by_id,
    get_conversation_by_response_id,
    get_conversation_by_ancestor_id,
    get_conversations_by_project,
    get_conversations_count_by_project,
    create_conversation,
    delete_conversation,
)
from app.models import OpenAIConversationCreate
from app.tests.utils.utils import get_project, get_organization


def generate_openai_id(prefix: str, length: int = 40) -> str:
    """Generate a realistic ID similar to OpenAI's format (alphanumeric only)"""
    chars = string.ascii_lowercase + string.digits
    random_part = "".join(secrets.choice(chars) for _ in range(length))
    return f"{prefix}{random_part}"


def test_get_conversation_by_id_success(db: Session):
    """Test successful conversation retrieval by ID."""
    project = get_project(db)
    organization = get_organization(db)

    conversation_data = OpenAIConversationCreate(
        response_id=generate_openai_id("resp_", 40),
        ancestor_response_id=generate_openai_id("resp_", 40),
        previous_response_id=None,
        user_question="What is the capital of Japan?",
        response="The capital of Japan is Tokyo.",
        model="gpt-4o",
        assistant_id=generate_openai_id("asst_", 20),
        project_id=project.id,
    )

    # Create the conversation in the database
    conversation = create_conversation(
        session=db,
        conversation=conversation_data,
        project_id=project.id,
        organization_id=organization.id,
    )

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
    organization = get_organization(db)

    conversation_data = OpenAIConversationCreate(
        response_id=generate_openai_id("resp_", 40),
        ancestor_response_id=generate_openai_id("resp_", 40),
        previous_response_id=None,
        user_question="What is the capital of Japan?",
        response="The capital of Japan is Tokyo.",
        model="gpt-4o",
        assistant_id=generate_openai_id("asst_", 20),
        project_id=project.id,
    )

    # Create the conversation in the database
    conversation = create_conversation(
        session=db,
        conversation=conversation_data,
        project_id=project.id,
        organization_id=organization.id,
    )

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
        project_id=project.id,
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
            project_id=project.id,
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
    organization = get_organization(db)

    # Create multiple conversations
    for i in range(5):
        conversation_data = OpenAIConversationCreate(
            response_id=generate_openai_id("resp_", 40),
            ancestor_response_id=None,
            previous_response_id=None,
            user_question=f"Test question {i}",
            response=f"Test response {i}",
            model="gpt-4o",
            assistant_id=generate_openai_id("asst_", 20),
            project_id=project.id,
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
        skip=1,
        limit=2,
    )

    assert len(conversations) <= 2


def test_delete_conversation_success(db: Session):
    """Test successful conversation deletion."""
    project = get_project(db)
    organization = get_organization(db)

    conversation_data = OpenAIConversationCreate(
        response_id=generate_openai_id("resp_", 40),
        ancestor_response_id=generate_openai_id("resp_", 40),
        previous_response_id=None,
        user_question="What is the capital of Japan?",
        response="The capital of Japan is Tokyo.",
        model="gpt-4o",
        assistant_id=generate_openai_id("asst_", 20),
        project_id=project.id,
    )

    # Create the conversation in the database first
    conversation = create_conversation(
        session=db,
        conversation=conversation_data,
        project_id=project.id,
        organization_id=organization.id,
    )

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
    organization = get_organization(db)

    conversation_data = OpenAIConversationCreate(
        response_id=generate_openai_id("resp_", 40),
        ancestor_response_id=generate_openai_id("resp_", 40),
        previous_response_id=None,
        user_question="What is the capital of Japan?",
        response="The capital of Japan is Tokyo.",
        model="gpt-4o",
        assistant_id=generate_openai_id("asst_", 20),
        project_id=project.id,
    )

    # Create the conversation in the database first
    conversation = create_conversation(
        session=db,
        conversation=conversation_data,
        project_id=project.id,
        organization_id=organization.id,
    )

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


def test_get_conversations_count_by_project_success(db: Session):
    """Test successful conversation count retrieval by project."""
    project = get_project(db)
    organization = get_organization(db)

    # Get initial count
    initial_count = get_conversations_count_by_project(
        session=db,
        project_id=project.id,
    )

    # Create multiple conversations
    for i in range(3):
        conversation_data = OpenAIConversationCreate(
            response_id=generate_openai_id("resp_", 40),
            ancestor_response_id=None,
            previous_response_id=None,
            user_question=f"Test question {i}",
            response=f"Test response {i}",
            model="gpt-4o",
            assistant_id=generate_openai_id("asst_", 20),
            project_id=project.id,
        )
        create_conversation(
            session=db,
            conversation=conversation_data,
            project_id=project.id,
            organization_id=organization.id,
        )

    # Get updated count
    updated_count = get_conversations_count_by_project(
        session=db,
        project_id=project.id,
    )

    assert updated_count == initial_count + 3


def test_get_conversations_count_by_project_excludes_deleted(db: Session):
    """Test that deleted conversations are not counted."""
    project = get_project(db)
    organization = get_organization(db)

    # Create a conversation
    conversation_data = OpenAIConversationCreate(
        response_id=generate_openai_id("resp_", 40),
        ancestor_response_id=None,
        previous_response_id=None,
        user_question="Test question",
        response="Test response",
        model="gpt-4o",
        assistant_id=generate_openai_id("asst_", 20),
        project_id=project.id,
    )

    conversation = create_conversation(
        session=db,
        conversation=conversation_data,
        project_id=project.id,
        organization_id=organization.id,
    )

    # Get count before deletion
    count_before = get_conversations_count_by_project(
        session=db,
        project_id=project.id,
    )

    # Delete the conversation
    delete_conversation(
        session=db,
        conversation_id=conversation.id,
        project_id=project.id,
    )

    # Get count after deletion
    count_after = get_conversations_count_by_project(
        session=db,
        project_id=project.id,
    )

    assert count_after == count_before - 1


def test_get_conversations_count_by_project_different_projects(db: Session):
    """Test that count is isolated by project."""
    project1 = get_project(db)
    organization = get_organization(db)

    # Get another project (assuming there are multiple projects in test data)
    project2 = (
        get_project(db, "Dalgo")
        if project1.name == "Glific"
        else get_project(db, "Glific")
    )

    if not project2 or project2.id == project1.id:
        pytest.skip("Need at least 2 different projects for this test")

    # Create conversation in project1
    conversation_data1 = OpenAIConversationCreate(
        response_id=generate_openai_id("resp_", 40),
        ancestor_response_id=None,
        previous_response_id=None,
        user_question="Test question 1",
        response="Test response 1",
        model="gpt-4o",
        assistant_id=generate_openai_id("asst_", 20),
        project_id=project1.id,
    )

    create_conversation(
        session=db,
        conversation=conversation_data1,
        project_id=project1.id,
        organization_id=organization.id,
    )

    # Create conversation in project2
    conversation_data2 = OpenAIConversationCreate(
        response_id=generate_openai_id("resp_", 40),
        ancestor_response_id=None,
        previous_response_id=None,
        user_question="Test question 2",
        response="Test response 2",
        model="gpt-4o",
        assistant_id=generate_openai_id("asst_", 20),
        project_id=project2.id,
    )

    create_conversation(
        session=db,
        conversation=conversation_data2,
        project_id=project2.id,
        organization_id=organization.id,
    )

    # Get counts for both projects
    count1 = get_conversations_count_by_project(
        session=db,
        project_id=project1.id,
    )

    count2 = get_conversations_count_by_project(
        session=db,
        project_id=project2.id,
    )

    # Both should have at least 1 conversation (the one we just created)
    assert count1 >= 1
    assert count2 >= 1
