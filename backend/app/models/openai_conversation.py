from datetime import datetime
from typing import Optional
import re

from pydantic import field_validator
from sqlmodel import Field, Relationship, SQLModel

from app.core.util import now


def validate_response_id_pattern(v: str) -> str:
    """Shared validation function for response ID patterns"""
    if v is None:
        return v
    if not re.match(r"^resp_[a-zA-Z0-9]{10,}$", v):
        raise ValueError(
            "response_id fields must follow pattern: resp_ followed by at least 10 alphanumeric characters"
        )
    return v


def validate_assistant_id_pattern(v: str) -> str:
    """Shared validation function for assistant ID patterns"""
    if v is None:
        return v
    if not re.match(r"^asst_[a-zA-Z0-9]{10,}$", v):
        raise ValueError(
            "assistant_id must follow pattern: asst_ followed by at least 10 alphanumeric characters"
        )
    return v


class OpenAIConversationBase(SQLModel):
    # usually follow the pattern of resp_688704e41190819db512c30568xxxxxxx
    response_id: str = Field(index=True, min_length=10)
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

    @field_validator("response_id", "ancestor_response_id", "previous_response_id")
    @classmethod
    def validate_response_ids(cls, v):
        return validate_response_id_pattern(v)

    @field_validator("assistant_id")
    @classmethod
    def validate_assistant_id(cls, v):
        return validate_assistant_id_pattern(v)


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
    # usually follow the pattern of resp_688704e41190819db512c30568dcaebc0a42e02be2c2c49b
    response_id: str = Field(min_length=10)
    ancestor_response_id: Optional[str] = Field(
        default=None, description="Ancestor response ID for conversation threading"
    )
    previous_response_id: Optional[str] = Field(
        default=None, description="Previous response ID in the conversation"
    )
    user_question: str = Field(description="User's question/input", min_length=1)
    response: Optional[str] = Field(default=None, description="AI response")
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

    @field_validator("response_id", "ancestor_response_id", "previous_response_id")
    @classmethod
    def validate_response_ids(cls, v):
        return validate_response_id_pattern(v)

    @field_validator("assistant_id")
    @classmethod
    def validate_assistant_id(cls, v):
        return validate_assistant_id_pattern(v)


class OpenAIConversationPublic(OpenAIConversationBase):
    """Public model for OpenAIConversation without sensitive fields"""

    id: int
    inserted_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True
        use_enum_values = True
