import logging

from fastapi import HTTPException
from sqlmodel import Session, and_, select
from typing import List, Optional

from app.core.util import now
from app.models import OpenAI_Conversation, OpenAIConversationCreate

logger = logging.getLogger(__name__)


def create_openai_conversation(
    session: Session, data: OpenAIConversationCreate
) -> OpenAI_Conversation:
    conversation = OpenAI_Conversation(**data.model_dump())
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def get_openai_conversation_by_id(
    session: Session, openai_conversation_id: str, project_id: int
) -> Optional[OpenAI_Conversation]:
    """Get an openai_conversation by its OpenAI openai_conversation ID and project ID."""
    statement = select(OpenAI_Conversation).where(
        and_(
            OpenAI_Conversation.id == openai_conversation_id,
            OpenAI_Conversation.project_id == project_id,
            OpenAI_Conversation.is_deleted == False,
        )
    )
    return session.exec(statement).first()


def get_openai_conversation_by_response_id(
    session: Session, response_id: str, project_id: int
) -> Optional[OpenAI_Conversation]:
    """Get an openai_conversation by its OpenAI response ID and project ID."""
    statement = select(OpenAI_Conversation).where(
        and_(
            OpenAI_Conversation.response_id == response_id,
            OpenAI_Conversation.project_id == project_id,
            OpenAI_Conversation.is_deleted == False,
        )
    )
    return session.exec(statement).first()


def get_openai_conversations_by_ancestor(
    session: Session, ancestor_response_id: str, project_id: int
) -> list[OpenAI_Conversation]:
    """Get all openai_conversations by ancestor_response_id."""
    statement = select(OpenAI_Conversation).where(
        and_(
            OpenAI_Conversation.ancestor_response_id == ancestor_response_id,
            OpenAI_Conversation.project_id == project_id,
            OpenAI_Conversation.is_deleted == False,
        )
    )
    return session.exec(statement).all()


def get_all_openai_conversations(
    session: Session, project_id: int, skip: int = 0, limit: int = 100
) -> List[OpenAI_Conversation]:
    """
    Return all openai conversations for a given project and organization, with optional pagination.
    """
    statement = (
        select(OpenAI_Conversation)
        .where(
            OpenAI_Conversation.project_id == project_id,
            OpenAI_Conversation.is_deleted == False,
        )
        .offset(skip)
        .limit(limit)
    )
    results = session.exec(statement).all()
    return results


def delete_openai_conversation(
    session: Session,
    conversation_id: int,
    project_id: int,
) -> OpenAI_Conversation:
    """
    Soft delete an conversation by updating is_deleted flag.
    """
    existing_conversation = get_openai_conversation_by_id(
        session, conversation_id, project_id
    )
    if not existing_conversation:
        logger.warning(
            f"[delete_openai_conversation] Conversation {conversation_id} not found | project_id: {project_id}"
        )
        raise HTTPException(status_code=404, detail="Conversation not found.")

    existing_conversation.is_deleted = True
    existing_conversation.deleted_at = now()
    session.add(existing_conversation)
    session.commit()
    session.refresh(existing_conversation)

    logger.info(
        f"[delete_openai_conversation] Conversation {conversation_id} soft deleted successfully. | project_id: {project_id}"
    )
    return existing_conversation
