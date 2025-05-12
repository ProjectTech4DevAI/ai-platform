from typing import Dict, Any, Optional
import sqlalchemy as sa
from sqlalchemy.ext.mutable import MutableDict
from sqlmodel import Field, Relationship, SQLModel
from datetime import datetime

from app.core.util import now


class CredsBase(SQLModel):
    organization_id: int = Field(foreign_key="organization.id")
    project_id: Optional[int] = Field(default=None, foreign_key="project.id")
    is_active: bool = True


class CredsCreate(CredsBase):
    """Create new credentials for an organization.
    The credential field should be a dictionary mapping provider names to their credentials.
    Example: {"openai": {"api_key": "..."}, "gemini": {"api_key": "..."}}
    """

    credential: Dict[str, Any] = Field(
        default=None,
        sa_column=sa.Column(MutableDict.as_mutable(sa.JSON)),
        description="Dictionary mapping provider names to their credentials",
    )


class CredsUpdate(SQLModel):
    """Update credentials for an organization.
    Can update a specific provider's credentials or add a new provider.
    """

    provider: str = Field(
        description="Name of the provider to update/add credentials for"
    )
    credential: Dict[str, Any] = Field(
        sa_column=sa.Column(MutableDict.as_mutable(sa.JSON)),
        description="Credentials for the specified provider",
    )
    is_active: Optional[bool] = Field(
        default=None, description="Whether the credentials are active"
    )
    project_id: Optional[int] = Field(
        default=None, description="Project ID to associate with these credentials"
    )


class Credential(CredsBase, table=True):
    """Database model for storing provider credentials.
    Each row represents credentials for a single provider.
    """

    id: int = Field(default=None, primary_key=True)
    provider: str = Field(
        index=True, description="Provider name like 'openai', 'gemini'"
    )
    credential: Dict[str, Any] = Field(
        sa_column=sa.Column(MutableDict.as_mutable(sa.JSON)),
        description="Provider-specific credentials (e.g., API keys)",
    )
    inserted_at: datetime = Field(
        default_factory=now,
        sa_column=sa.Column(sa.DateTime, default=datetime.utcnow),
    )
    updated_at: datetime = Field(
        default_factory=now,
        sa_column=sa.Column(sa.DateTime, onupdate=datetime.utcnow),
    )
    deleted_at: Optional[datetime] = Field(
        default=None, sa_column=sa.Column(sa.DateTime, nullable=True)
    )

    organization: Optional["Organization"] = Relationship(back_populates="creds")
    project: Optional["Project"] = Relationship(back_populates="creds")


class CredsPublic(CredsBase):
    """Public representation of credentials, excluding sensitive information."""

    id: int
    provider: str
    credential: Dict[str, Any]
    inserted_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]
