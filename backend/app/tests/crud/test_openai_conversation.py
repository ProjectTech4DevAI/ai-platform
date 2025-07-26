import pytest
from uuid import uuid4
from sqlmodel import Session

from app.crud.openai_conversation import (
    get_conversation_by_id,
    get_conversation_by_response_id,
    get_conversations_by_project,
    get_conversations_by_assistant,
    get_conversation_thread,
    create_conversation,
    update_conversation,
    delete_conversation,
    upsert_conversation,
)
from app.models import OpenAIConversationCreate, OpenAIConversationUpdate
from app.tests.utils.conversation import get_conversation
from app.tests.utils.utils import get_project, get_organization


@pytest.fixture
def conversation_create_data():
    return OpenAIConversationCreate(
        response_id=f"resp_{uuid4()}",
        ancestor_response_id=None,
        previous_response_id=None,
        user_question="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        assistant_id=f"asst_{uuid4()}",
    )


@pytest.fixture
def conversation_update_data():
    return OpenAIConversationUpdate(
        response="The capital of France is Paris, which is a beautiful city.",
        model="gpt-4o-mini",
    )


def test_create_conversation_success(
    db: Session, conversation_create_data: OpenAIConversationCreate
):
    """Test successful conversation creation."""
    project = get_project(db)
    organization = get_organization(db)

    conversation = create_conversation(
        session=db,
        conversation=conversation_create_data,
        project_id=project.id,
        organization_id=organization.id,
    )

    assert conversation is not None
    assert conversation.response_id == conversation_create_data.response_id
    assert conversation.user_question == conversation_create_data.user_question
    assert conversation.response == conversation_create_data.response
    assert conversation.model == conversation_create_data.model
    assert conversation.assistant_id == conversation_create_data.assistant_id
    assert conversation.project_id == project.id
    assert conversation.organization_id == organization.id
    assert conversation.is_deleted is False
    assert conversation.deleted_at is None


def test_get_conversation_by_id_success(db: Session):
    """Test successful conversation retrieval by ID."""
    conversation = get_conversation(db)
    project = get_project(db)

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
    conversation = get_conversation(db)
    project = get_project(db)

    retrieved_conversation = get_conversation_by_response_id(
        session=db,
        response_id=conversation.response_id,
        project_id=project.id,
    )

    assert retrieved_conversation is not None
    assert retrieved_conversation.response_id == conversation.response_id
    assert retrieved_conversation.id == conversation.id


def test_get_conversation_by_response_id_not_found(db: Session):
    """Test conversation retrieval by non-existent response ID."""
    project = get_project(db)

    retrieved_conversation = get_conversation_by_response_id(
        session=db,
        response_id="non_existent_response_id",
        project_id=project.id,
    )

    assert retrieved_conversation is None


def test_get_conversations_by_project_success(db: Session):
    """Test successful conversation listing by project."""
    project = get_project(db)
    organization = get_organization(db)

    # Create multiple conversations directly
    from app.models import OpenAIConversationCreate
    from app.crud.openai_conversation import create_conversation
    from uuid import uuid4

    for i in range(3):
        conversation_data = OpenAIConversationCreate(
            response_id=f"resp_{uuid4()}",
            ancestor_response_id=None,
            previous_response_id=None,
            user_question=f"Test question {i}",
            response=f"Test response {i}",
            model="gpt-4o",
            assistant_id=f"asst_{uuid4()}",
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
        skip=0,
        limit=10,
    )

    assert len(conversations) >= 3
    for conversation in conversations:
        assert conversation.project_id == project.id
        assert conversation.is_deleted is False


def test_get_conversations_by_project_with_pagination(db: Session):
    """Test conversation listing by project with pagination."""
    # Create multiple conversations
    for _ in range(5):
        get_conversation(db)

    project = get_project(db)

    conversations = get_conversations_by_project(
        session=db,
        project_id=project.id,
        skip=2,
        limit=2,
    )

    assert len(conversations) <= 2


def test_get_conversations_by_assistant_success(db: Session):
    """Test successful conversation listing by assistant."""
    conversation = get_conversation(db)
    project = get_project(db)

    conversations = get_conversations_by_assistant(
        session=db,
        assistant_id=conversation.assistant_id,
        project_id=project.id,
        skip=0,
        limit=10,
    )

    assert len(conversations) >= 1
    for conv in conversations:
        assert conv.assistant_id == conversation.assistant_id
        assert conv.project_id == project.id
        assert conv.is_deleted is False


def test_get_conversations_by_assistant_not_found(db: Session):
    """Test conversation listing by non-existent assistant."""
    project = get_project(db)

    conversations = get_conversations_by_assistant(
        session=db,
        assistant_id="non_existent_assistant_id",
        project_id=project.id,
        skip=0,
        limit=10,
    )

    assert len(conversations) == 0


def test_get_conversation_thread_success(db: Session):
    """Test successful conversation thread retrieval."""
    conversation = get_conversation(db)
    project = get_project(db)

    thread_conversations = get_conversation_thread(
        session=db,
        response_id=conversation.response_id,
        project_id=project.id,
    )

    assert isinstance(thread_conversations, list)
    assert len(thread_conversations) >= 1
    assert thread_conversations[0].response_id == conversation.response_id


def test_get_conversation_thread_not_found(db: Session):
    """Test conversation thread retrieval with non-existent response ID."""
    project = get_project(db)

    thread_conversations = get_conversation_thread(
        session=db,
        response_id="non_existent_response_id",
        project_id=project.id,
    )

    assert isinstance(thread_conversations, list)
    assert len(thread_conversations) == 0


def test_update_conversation_success(
    db: Session, conversation_update_data: OpenAIConversationUpdate
):
    """Test successful conversation update."""
    conversation = get_conversation(db)
    project = get_project(db)

    updated_conversation = update_conversation(
        session=db,
        conversation_id=conversation.id,
        project_id=project.id,
        conversation_update=conversation_update_data,
    )

    assert updated_conversation is not None
    assert updated_conversation.response == conversation_update_data.response
    assert updated_conversation.model == conversation_update_data.model
    assert updated_conversation.id == conversation.id


def test_update_conversation_not_found(
    db: Session, conversation_update_data: OpenAIConversationUpdate
):
    """Test conversation update with non-existent ID."""
    project = get_project(db)

    updated_conversation = update_conversation(
        session=db,
        conversation_id=99999,
        project_id=project.id,
        conversation_update=conversation_update_data,
    )

    assert updated_conversation is None


def test_delete_conversation_success(db: Session):
    """Test successful conversation deletion."""
    conversation = get_conversation(db)
    project = get_project(db)

    deleted_conversation = delete_conversation(
        session=db,
        conversation_id=conversation.id,
        project_id=project.id,
    )

    assert deleted_conversation is not None
    assert deleted_conversation.is_deleted is True
    assert deleted_conversation.deleted_at is not None
    assert deleted_conversation.id == conversation.id


def test_delete_conversation_not_found(db: Session):
    """Test conversation deletion with non-existent ID."""
    project = get_project(db)

    deleted_conversation = delete_conversation(
        session=db,
        conversation_id=99999,
        project_id=project.id,
    )

    assert deleted_conversation is None


def test_upsert_conversation_create_new(
    db: Session, conversation_create_data: OpenAIConversationCreate
):
    """Test upsert conversation creates new conversation."""
    project = get_project(db)
    organization = get_organization(db)

    conversation = upsert_conversation(
        session=db,
        conversation=conversation_create_data,
        project_id=project.id,
        organization_id=organization.id,
    )

    assert conversation is not None
    assert conversation.response_id == conversation_create_data.response_id
    assert conversation.user_question == conversation_create_data.user_question


def test_upsert_conversation_update_existing(
    db: Session, conversation_create_data: OpenAIConversationCreate
):
    """Test upsert conversation updates existing conversation."""
    project = get_project(db)
    organization = get_organization(db)

    # First create a conversation
    conversation1 = upsert_conversation(
        session=db,
        conversation=conversation_create_data,
        project_id=project.id,
        organization_id=organization.id,
    )

    # Update the data and upsert again
    conversation_create_data.response = "Updated response"
    conversation_create_data.model = "gpt-4o-mini"

    conversation2 = upsert_conversation(
        session=db,
        conversation=conversation_create_data,
        project_id=project.id,
        organization_id=organization.id,
    )

    assert conversation2 is not None
    assert conversation2.id == conversation1.id  # Same conversation
    assert conversation2.response == "Updated response"
    assert conversation2.model == "gpt-4o-mini"
    assert conversation2.response_id == conversation1.response_id


def test_conversation_soft_delete_behavior(db: Session):
    """Test that soft deleted conversations are not returned by queries."""
    conversation = get_conversation(db)
    project = get_project(db)

    # Delete the conversation
    delete_conversation(
        session=db,
        conversation_id=conversation.id,
        project_id=project.id,
    )

    # Try to retrieve it by ID
    retrieved_conversation = get_conversation_by_id(
        session=db,
        conversation_id=conversation.id,
        project_id=project.id,
    )

    assert retrieved_conversation is None

    # Try to retrieve it by response ID
    retrieved_conversation = get_conversation_by_response_id(
        session=db,
        response_id=conversation.response_id,
        project_id=project.id,
    )

    assert retrieved_conversation is None

    # Check that it's not in the project list
    conversations = get_conversations_by_project(
        session=db,
        project_id=project.id,
        skip=0,
        limit=10,
    )

    conversation_ids = [conv.id for conv in conversations]
    assert conversation.id not in conversation_ids
