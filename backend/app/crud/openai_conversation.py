import logging
from typing import Optional, List

from sqlmodel import Session, and_, select

from app.models import (
    OpenAIConversation,
    OpenAIConversationCreate,
    OpenAIConversationUpdate,
)
from app.core.util import now

logger = logging.getLogger(__name__)


def get_conversation_by_id(
    session: Session, conversation_id: int, project_id: int
) -> Optional[OpenAIConversation]:
    """Get a conversation by its ID and project ID."""
    statement = select(OpenAIConversation).where(
        and_(
            OpenAIConversation.id == conversation_id,
            OpenAIConversation.project_id == project_id,
            OpenAIConversation.is_deleted == False,
        )
    )
    return session.exec(statement).first()


def get_conversation_by_response_id(
    session: Session, response_id: str, project_id: int
) -> Optional[OpenAIConversation]:
    """Get a conversation by its OpenAI response ID and project ID."""
    statement = select(OpenAIConversation).where(
        and_(
            OpenAIConversation.response_id == response_id,
            OpenAIConversation.project_id == project_id,
            OpenAIConversation.is_deleted == False,
        )
    )
    return session.exec(statement).first()


def get_conversations_by_project(
    session: Session,
    project_id: int,
    skip: int = 0,
    limit: int = 100,
) -> List[OpenAIConversation]:
    """
    Return all conversations for a given project, with optional pagination.
    """
    statement = (
        select(OpenAIConversation)
        .where(
            OpenAIConversation.project_id == project_id,
            OpenAIConversation.is_deleted == False,
        )
        .order_by(OpenAIConversation.inserted_at.desc())
        .offset(skip)
        .limit(limit)
    )
    results = session.exec(statement).all()
    return results


def get_conversations_by_assistant(
    session: Session,
    assistant_id: str,
    project_id: int,
    skip: int = 0,
    limit: int = 100,
) -> List[OpenAIConversation]:
    """
    Return all conversations for a given assistant and project, with optional pagination.
    """
    statement = (
        select(OpenAIConversation)
        .where(
            OpenAIConversation.assistant_id == assistant_id,
            OpenAIConversation.project_id == project_id,
            OpenAIConversation.is_deleted == False,
        )
        .order_by(OpenAIConversation.inserted_at.desc())
        .offset(skip)
        .limit(limit)
    )
    results = session.exec(statement).all()
    return results


def get_conversation_thread(
    session: Session,
    response_id: str,
    project_id: int,
) -> List[OpenAIConversation]:
    """
    Get the full conversation thread starting from a given response ID.
    This includes all ancestor and previous responses in the conversation chain.
    """
    # First, find the root of the conversation thread
    root_response_id = response_id
    current_conversation = get_conversation_by_response_id(
        session, response_id, project_id
    )

    if not current_conversation:
        return []

    # Find the root of the conversation thread
    while current_conversation.ancestor_response_id:
        root_conversation = get_conversation_by_response_id(
            session, current_conversation.ancestor_response_id, project_id
        )
        if not root_conversation:
            break
        root_response_id = current_conversation.ancestor_response_id
        current_conversation = root_conversation

    # Now get all conversations in the thread
    thread_conversations = []
    current_response_id = root_response_id

    while current_response_id:
        conversation = get_conversation_by_response_id(
            session, current_response_id, project_id
        )
        if not conversation:
            break
        thread_conversations.append(conversation)
        current_response_id = conversation.previous_response_id

    return thread_conversations


def create_conversation(
    session: Session,
    conversation: OpenAIConversationCreate,
    project_id: int,
    organization_id: int,
) -> OpenAIConversation:
    """
    Create a new conversation in the database.
    """
    db_conversation = OpenAIConversation(
        **conversation.model_dump(),
        project_id=project_id,
        organization_id=organization_id,
    )
    session.add(db_conversation)
    session.commit()
    session.refresh(db_conversation)

    logger.info(
        f"Created conversation with response_id={db_conversation.response_id}, "
        f"assistant_id={db_conversation.assistant_id}, project_id={project_id}"
    )

    return db_conversation


def update_conversation(
    session: Session,
    conversation_id: int,
    project_id: int,
    conversation_update: OpenAIConversationUpdate,
) -> Optional[OpenAIConversation]:
    """
    Update an existing conversation.
    """
    db_conversation = get_conversation_by_id(session, conversation_id, project_id)
    if not db_conversation:
        return None

    update_data = conversation_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_conversation, field, value)

    db_conversation.updated_at = now()
    session.add(db_conversation)
    session.commit()
    session.refresh(db_conversation)

    logger.info(
        f"Updated conversation with id={conversation_id}, "
        f"response_id={db_conversation.response_id}, project_id={project_id}"
    )

    return db_conversation


def delete_conversation(
    session: Session,
    conversation_id: int,
    project_id: int,
) -> Optional[OpenAIConversation]:
    """
    Soft delete a conversation by marking it as deleted.
    """
    db_conversation = get_conversation_by_id(session, conversation_id, project_id)
    if not db_conversation:
        return None

    db_conversation.is_deleted = True
    db_conversation.deleted_at = now()
    session.add(db_conversation)
    session.commit()
    session.refresh(db_conversation)

    logger.info(
        f"Deleted conversation with id={conversation_id}, "
        f"response_id={db_conversation.response_id}, project_id={project_id}"
    )

    return db_conversation


def upsert_conversation(
    session: Session,
    conversation: OpenAIConversationCreate,
    project_id: int,
    organization_id: int,
) -> OpenAIConversation:
    """
    Create a new conversation or update existing one if response_id already exists.
    """
    existing_conversation = get_conversation_by_response_id(
        session, conversation.response_id, project_id
    )

    if existing_conversation:
        # Update existing conversation
        update_data = conversation.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(existing_conversation, field, value)

        existing_conversation.updated_at = now()
        session.add(existing_conversation)
        session.commit()
        session.refresh(existing_conversation)

        logger.info(
            f"Updated existing conversation with response_id={conversation.response_id}, "
            f"project_id={project_id}"
        )

        return existing_conversation
    else:
        # Create new conversation
        return create_conversation(session, conversation, project_id, organization_id)
