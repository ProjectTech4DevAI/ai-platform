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
    input_tokens: Optional[int] = Field(
        default=None, description="Number of input tokens"
    )
    output_tokens: Optional[int] = Field(
        default=None, description="Number of output tokens"
    )
    total_tokens: Optional[int] = Field(
        default=None, description="Total number of tokens"
    )
    assistant_id: Optional[str] = Field(
        default=None, description="The assistant ID used"
    )
    project_id: Optional[int] = Field(default=None, description="The project ID")
    organization_id: Optional[int] = Field(
        default=None, description="The organization ID"
    )


class OpenAIConversationCreate(OpenAIConversationBase):
    pass  # Used for requests, no `id` or timestamps


class OpenAIConversationUpdate(SQLModel):
    response_id: Optional[str] = None
    ancestor_response_id: Optional[str] = None
    previous_response_id: Optional[str] = None
    user_question: Optional[str] = None
    assistant_response: Optional[str] = None
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    assistant_id: Optional[str] = None
    project_id: Optional[int] = None
    organization_id: Optional[int] = None


class OpenAIConversationPublic(OpenAIConversationBase):
    id: int
    inserted_at: datetime
    updated_at: datetime


class OpenAI_Conversation(OpenAIConversationBase, table=True):
    id: int = Field(default=None, primary_key=True)
    inserted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
