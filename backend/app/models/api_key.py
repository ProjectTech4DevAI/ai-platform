from uuid import UUID, uuid4
import secrets
import base64
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

from app.core.util import now


class APIKeyBase(SQLModel):
    organization_id: int = Field(
        foreign_key="organization.id", nullable=False, ondelete="CASCADE"
    )
    project_id: int = Field(
        foreign_key="project.id", nullable=False, ondelete="CASCADE"
    )
    user_id: int = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")


class APIKeyPublic(APIKeyBase):
    id: UUID
    key_prefix: str  # Expose key_id for display (partial key identifier)
    inserted_at: datetime
    updated_at: datetime


class APIKeyCreateResponse(APIKeyPublic):
    """Response model when creating an API key includes the raw key only once"""

    key: str


class APIKey(APIKeyBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    key_prefix: str = Field(
        unique=True, index=True, nullable=False
    )  # Unique identifier from the key
    key_hash: str = Field(nullable=False)  # bcrypt hash of the secret portion

    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)
    is_deleted: bool = Field(default=False, nullable=False)
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)
