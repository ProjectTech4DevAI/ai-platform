from sqlmodel import Session, and_, select
from typing import List, Optional
from app.models import OpenAI_Conversation, OpenAIConversationCreate


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


def delete_openai_conversation(session: Session, conversation_id: int) -> bool:
    conversation = get_openai_conversation_by_id(session, conversation_id)
    if not conversation:
        return False

    session.delete(conversation)
    session.commit()
    return True
