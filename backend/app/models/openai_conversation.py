from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, UTC


class OpenAIConversationBase(SQLModel):
    response_id: str = Field(index=True, min_length=10)
    # ancestor_response_id of first response will be itself
    ancestor_response_id: str = Field(index=True)
    previous_response_id: Optional[str] = Field(default=None, index=True)
    user_question: str = Field(description="The user's input question", min_length=1)
    response: Optional[str] = Field(description="The assistant's response")
    # there are models with small name like o1 and usually fine tuned models have long names
    model: str = Field(
        description="The model used for the response", min_length=1, max_length=150
    )
    # usually follow the pattern of asst_WD9bumYqTtpSvxxxxx
    assistant_id: Optional[str] = Field(
        default=None,
        description="The assistant ID used",
        min_length=10,
        max_length=50,
    )
    project_id: int = Field(
        foreign_key="project.id", nullable=False, ondelete="CASCADE"
    )
    organization_id: int = Field(
        foreign_key="organization.id", nullable=False, ondelete="CASCADE"
    )
    is_deleted: bool = Field(default=False, nullable=False)
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)


class OpenAIConversationCreate(OpenAIConversationBase):
    pass  # Used for requests, no `id` or timestamps


class OpenAIConversationPublic(OpenAIConversationBase):
    id: int
    inserted_at: datetime
    updated_at: datetime


class OpenAI_Conversation(OpenAIConversationBase, table=True):
    id: int = Field(default=None, primary_key=True)
    inserted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
