from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime


class OpenAIConversationBase(SQLModel):
    response_id: str = Field(index=True)
    ancestor_response_id: Optional[str] = Field(default=None, index=True)
    previous_response_id: Optional[str] = Field(default=None, index=True)


class OpenAIConversationCreate(OpenAIConversationBase):
    pass  # Used for requests, no `id` or timestamps


class OpenAIConversationUpdate(SQLModel):
    response_id: Optional[str] = None
    ancestor_response_id: Optional[str] = None
    previous_response_id: Optional[str] = None


class OpenAIConversationPublic(OpenAIConversationBase):
    id: int
    inserted_at: datetime
    updated_at: datetime


class OpenAI_Conversation(OpenAIConversationBase, table=True):
    id: int = Field(default=None, primary_key=True)
    inserted_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
