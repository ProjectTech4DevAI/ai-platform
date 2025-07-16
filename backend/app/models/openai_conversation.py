from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, UTC


class OpenAIConversationBase(SQLModel):
    response_id: str = Field(index=True)
    ancestor_response_id: Optional[str] = Field(default=None, index=True)
    previous_response_id: Optional[str] = Field(default=None, index=True)
    user_question: str = Field(description="The user's input question")
    assistant_response: str = Field(description="The assistant's response")
    model: str = Field(description="The model used for the response")
    assistant_id: Optional[str] = Field(
        default=None, description="The assistant ID used"
    )
    project_id: int = Field(foreign_key="project.id")
    organization_id: int = Field(foreign_key="organization.id")


class OpenAIConversationCreate(OpenAIConversationBase):
    pass  # Used for requests, no `id` or timestamps


class OpenAIConversationUpdate(SQLModel):
    response_id: Optional[str] = None
    ancestor_response_id: Optional[str] = None
    previous_response_id: Optional[str] = None
    user_question: Optional[str] = None
    assistant_response: Optional[str] = None
    model: Optional[str] = None
    assistant_id: Optional[str] = None
    project_id: Optional[int] = Field(default=None, foreign_key="project.id")
    organization_id: Optional[int] = Field(default=None, foreign_key="organization.id")


class OpenAIConversationPublic(OpenAIConversationBase):
    id: int
    inserted_at: datetime
    updated_at: datetime


class OpenAI_Conversation(OpenAIConversationBase, table=True):
    id: int = Field(default=None, primary_key=True)
    inserted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
