import uuid
import secrets
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


class APIKeyBase(SQLModel):
    organization_id: int = Field(
        foreign_key="organization.id", nullable=False, ondelete="CASCADE"
    )
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    key: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32), unique=True, index=True
    )


class APIKeyPublic(APIKeyBase):
    id: int
    inserted_at: datetime


class APIKey(APIKeyBase, table=True):
    id: int = Field(default=None, primary_key=True)
    inserted_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    is_deleted: bool = Field(default=False, nullable=False)
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)

    # Relationships
    organization: "Organization" = Relationship(back_populates="api_keys")
    user: "User" = Relationship(back_populates="api_keys")
