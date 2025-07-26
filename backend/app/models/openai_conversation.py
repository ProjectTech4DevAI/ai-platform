from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

from app.core.util import now


class OpenAIConversationBase(SQLModel):
    response_id: str = Field(index=True, description="OpenAI response ID")
    ancestor_response_id: Optional[str] = Field(
        default=None,
        index=True,
        description="Ancestor response ID for conversation threading",
    )
    previous_response_id: Optional[str] = Field(
        default=None, index=True, description="Previous response ID in the conversation"
    )
    user_question: str = Field(description="User's question/input")
    response: Optional[str] = Field(default=None, description="AI response")
    model: str = Field(description="Model used for the response")
    assistant_id: str = Field(description="Assistant ID used for the response")
    project_id: int = Field(
        foreign_key="project.id", nullable=False, ondelete="CASCADE"
    )
    organization_id: int = Field(
        foreign_key="organization.id", nullable=False, ondelete="CASCADE"
    )


class OpenAIConversation(OpenAIConversationBase, table=True):
    __tablename__ = "openai_conversation"

    id: int = Field(default=None, primary_key=True)
    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)
    is_deleted: bool = Field(default=False, nullable=False)
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)

    # Relationships
    project: "Project" = Relationship(back_populates="openai_conversations")
    organization: "Organization" = Relationship(back_populates="openai_conversations")


class OpenAIConversationCreate(SQLModel):
    response_id: str = Field(description="OpenAI response ID")
    ancestor_response_id: Optional[str] = Field(
        default=None, description="Ancestor response ID for conversation threading"
    )
    previous_response_id: Optional[str] = Field(
        default=None, description="Previous response ID in the conversation"
    )
    user_question: str = Field(description="User's question/input", min_length=1)
    response: Optional[str] = Field(default=None, description="AI response")
    model: str = Field(description="Model used for the response", min_length=1)
    assistant_id: str = Field(
        description="Assistant ID used for the response", min_length=1
    )


class OpenAIConversationUpdate(SQLModel):
    response_id: Optional[str] = Field(default=None, description="OpenAI response ID")
    ancestor_response_id: Optional[str] = Field(
        default=None, description="Ancestor response ID for conversation threading"
    )
    previous_response_id: Optional[str] = Field(
        default=None, description="Previous response ID in the conversation"
    )
    user_question: Optional[str] = Field(
        default=None, description="User's question/input", min_length=1
    )
    response: Optional[str] = Field(default=None, description="AI response")
    model: Optional[str] = Field(
        default=None, description="Model used for the response", min_length=1
    )
    assistant_id: Optional[str] = Field(
        default=None, description="Assistant ID used for the response", min_length=1
    )
