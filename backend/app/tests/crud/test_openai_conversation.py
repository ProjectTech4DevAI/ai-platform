import pytest
from uuid import uuid4
from sqlmodel import Session

from app.crud.openai_conversation import (
    get_conversation_by_id,
    get_conversation_by_response_id,
    get_conversation_by_ancestor_id,
    get_conversations_by_project,
    create_conversation,
    delete_conversation,
    set_ancestor_response_id,
)
from app.models import OpenAIConversationCreate
from app.tests.utils.conversation import get_conversation
from app.tests.utils.utils import get_project, get_organization


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
    ancestor_response_id = f"resp_{uuid4()}"
    conversation_data = OpenAIConversationCreate(
        response_id=f"resp_{uuid4()}",
        ancestor_response_id=ancestor_response_id,
        previous_response_id=None,
        user_question="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        assistant_id=f"asst_{uuid4()}",
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
    conversation = get_conversation(db)
    project = get_project(db)

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
    conversation = get_conversation(db)
    project = get_project(db)

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


def test_set_ancestor_response_id_no_previous_response(db: Session):
    """Test set_ancestor_response_id when previous_response_id is None."""
    project = get_project(db)
    current_response_id = f"resp_{uuid4()}"

    ancestor_id = set_ancestor_response_id(
        session=db,
        current_response_id=current_response_id,
        previous_response_id=None,
        project_id=project.id,
    )

    assert ancestor_id == current_response_id


def test_set_ancestor_response_id_previous_not_found(db: Session):
    """Test set_ancestor_response_id when previous_response_id is not found in DB."""
    project = get_project(db)
    current_response_id = f"resp_{uuid4()}"
    previous_response_id = f"resp_{uuid4()}"

    ancestor_id = set_ancestor_response_id(
        session=db,
        current_response_id=current_response_id,
        previous_response_id=previous_response_id,
        project_id=project.id,
    )

    # When previous_response_id is not found, should return previous_response_id
    assert ancestor_id == previous_response_id


def test_set_ancestor_response_id_previous_found_with_ancestor(db: Session):
    """Test set_ancestor_response_id when previous_response_id is found and has an ancestor."""
    project = get_project(db)
    organization = get_organization(db)

    # Create a conversation chain: ancestor -> previous -> current
    ancestor_response_id = f"resp_{uuid4()}"

    # Create the ancestor conversation
    ancestor_conversation_data = OpenAIConversationCreate(
        response_id=ancestor_response_id,
        ancestor_response_id=ancestor_response_id,  # Self-referencing
        previous_response_id=None,
        user_question="Original question",
        response="Original response",
        model="gpt-4o",
        assistant_id=f"asst_{uuid4()}",
    )

    ancestor_conversation = create_conversation(
        session=db,
        conversation=ancestor_conversation_data,
        project_id=project.id,
        organization_id=organization.id,
    )

    # Create the previous conversation
    previous_response_id = f"resp_{uuid4()}"
    previous_conversation_data = OpenAIConversationCreate(
        response_id=previous_response_id,
        ancestor_response_id=ancestor_response_id,
        previous_response_id=ancestor_response_id,
        user_question="Previous question",
        response="Previous response",
        model="gpt-4o",
        assistant_id=f"asst_{uuid4()}",
    )

    previous_conversation = create_conversation(
        session=db,
        conversation=previous_conversation_data,
        project_id=project.id,
        organization_id=organization.id,
    )

    # Test the current conversation
    current_response_id = f"resp_{uuid4()}"
    ancestor_id = set_ancestor_response_id(
        session=db,
        current_response_id=current_response_id,
        previous_response_id=previous_response_id,
        project_id=project.id,
    )

    assert ancestor_id == ancestor_response_id


def test_set_ancestor_response_id_previous_found_without_ancestor(db: Session):
    """Test set_ancestor_response_id when previous_response_id is found but has no ancestor."""
    project = get_project(db)
    organization = get_organization(db)

    # Create a previous conversation without ancestor
    previous_response_id = f"resp_{uuid4()}"
    previous_conversation_data = OpenAIConversationCreate(
        response_id=previous_response_id,
        ancestor_response_id=None,  # No ancestor
        previous_response_id=None,
        user_question="Previous question",
        response="Previous response",
        model="gpt-4o",
        assistant_id=f"asst_{uuid4()}",
    )

    previous_conversation = create_conversation(
        session=db,
        conversation=previous_conversation_data,
        project_id=project.id,
        organization_id=organization.id,
    )

    # Test the current conversation
    current_response_id = f"resp_{uuid4()}"
    ancestor_id = set_ancestor_response_id(
        session=db,
        current_response_id=current_response_id,
        previous_response_id=previous_response_id,
        project_id=project.id,
    )

    # When previous conversation has no ancestor, should return None
    assert ancestor_id is None


def test_set_ancestor_response_id_different_project(db: Session):
    """Test set_ancestor_response_id respects project scoping."""
    project1 = get_project(db)
    organization = get_organization(db)

    # Create a second project with a different name
    from app.models import Project

    project2 = Project(
        name=f"test_project_{uuid4()}",
        description="Test project for scoping",
        is_active=True,
        organization_id=organization.id,
    )
    db.add(project2)
    db.commit()
    db.refresh(project2)

    # Create a conversation in project1
    previous_response_id = f"resp_{uuid4()}"
    previous_conversation_data = OpenAIConversationCreate(
        response_id=previous_response_id,
        ancestor_response_id=f"ancestor_{uuid4()}",
        previous_response_id=None,
        user_question="Previous question",
        response="Previous response",
        model="gpt-4o",
        assistant_id=f"asst_{uuid4()}",
    )

    create_conversation(
        session=db,
        conversation=previous_conversation_data,
        project_id=project1.id,
        organization_id=organization.id,
    )

    # Test looking for it in project2 (should not find it)
    current_response_id = f"resp_{uuid4()}"
    ancestor_id = set_ancestor_response_id(
        session=db,
        current_response_id=current_response_id,
        previous_response_id=previous_response_id,
        project_id=project2.id,
    )

    # Should return previous_response_id since it's not found in project2
    assert ancestor_id == previous_response_id


def test_set_ancestor_response_id_complex_chain(db: Session):
    """Test set_ancestor_response_id with a complex conversation chain."""
    project = get_project(db)
    organization = get_organization(db)

    # Create a complex chain: A -> B -> C -> D
    # A is the root ancestor
    response_a = f"resp_{uuid4()}"
    conversation_a_data = OpenAIConversationCreate(
        response_id=response_a,
        ancestor_response_id=response_a,  # Self-referencing
        previous_response_id=None,
        user_question="Question A",
        response="Response A",
        model="gpt-4o",
        assistant_id=f"asst_{uuid4()}",
    )

    create_conversation(
        session=db,
        conversation=conversation_a_data,
        project_id=project.id,
        organization_id=organization.id,
    )

    # B references A
    response_b = f"resp_{uuid4()}"
    conversation_b_data = OpenAIConversationCreate(
        response_id=response_b,
        ancestor_response_id=response_a,
        previous_response_id=response_a,
        user_question="Question B",
        response="Response B",
        model="gpt-4o",
        assistant_id=f"asst_{uuid4()}",
    )

    create_conversation(
        session=db,
        conversation=conversation_b_data,
        project_id=project.id,
        organization_id=organization.id,
    )

    # C references B
    response_c = f"resp_{uuid4()}"
    conversation_c_data = OpenAIConversationCreate(
        response_id=response_c,
        ancestor_response_id=response_a,  # Should inherit from B
        previous_response_id=response_b,
        user_question="Question C",
        response="Response C",
        model="gpt-4o",
        assistant_id=f"asst_{uuid4()}",
    )

    create_conversation(
        session=db,
        conversation=conversation_c_data,
        project_id=project.id,
        organization_id=organization.id,
    )

    # Test D referencing C
    response_d = f"resp_{uuid4()}"
    ancestor_id = set_ancestor_response_id(
        session=db,
        current_response_id=response_d,
        previous_response_id=response_c,
        project_id=project.id,
    )

    # Should return response_a (the root ancestor)
    assert ancestor_id == response_a


def test_create_conversation_success(db: Session):
    """Test successful conversation creation."""
    project = get_project(db)
    organization = get_organization(db)

    conversation_data = OpenAIConversationCreate(
        response_id=f"resp_{uuid4()}",
        ancestor_response_id=None,
        previous_response_id=None,
        user_question="Test question",
        response="Test response",
        model="gpt-4o",
        assistant_id=f"asst_{uuid4()}",
    )

    conversation = create_conversation(
        session=db,
        conversation=conversation_data,
        project_id=project.id,
        organization_id=organization.id,
    )

    assert conversation is not None
    assert conversation.response_id == conversation_data.response_id
    assert conversation.user_question == conversation_data.user_question
    assert conversation.response == conversation_data.response
    assert conversation.model == conversation_data.model
    assert conversation.assistant_id == conversation_data.assistant_id
    assert conversation.project_id == project.id
    assert conversation.organization_id == organization.id
    assert conversation.is_deleted is False
    assert conversation.deleted_at is None


def test_create_conversation_with_ancestor(db: Session):
    """Test conversation creation with ancestor and previous response IDs."""
    project = get_project(db)
    organization = get_organization(db)

    ancestor_response_id = f"resp_{uuid4()}"
    previous_response_id = f"resp_{uuid4()}"

    conversation_data = OpenAIConversationCreate(
        response_id=f"resp_{uuid4()}",
        ancestor_response_id=ancestor_response_id,
        previous_response_id=previous_response_id,
        user_question="Follow-up question",
        response="Follow-up response",
        model="gpt-4o",
        assistant_id=f"asst_{uuid4()}",
    )

    conversation = create_conversation(
        session=db,
        conversation=conversation_data,
        project_id=project.id,
        organization_id=organization.id,
    )

    assert conversation is not None
    assert conversation.ancestor_response_id == ancestor_response_id
    assert conversation.previous_response_id == previous_response_id
