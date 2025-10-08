from typing import Dict, Any, Optional
import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel
from datetime import datetime

from app.core.util import now


class CredsBase(SQLModel):
    organization_id: int = Field(
        foreign_key="organization.id", nullable=False, ondelete="CASCADE"
    )
    project_id: int = Field(
        default=None, foreign_key="project.id", nullable=False, ondelete="CASCADE"
    )
    is_active: bool = True


class CredsCreate(SQLModel):
    """Create new credentials for an organization.
    The credential field should be a dictionary mapping provider names to their credentials.
    Example: {"openai": {"api_key": "..."}, "langfuse": {"public_key": "..."}}
    """

    is_active: bool = True
    credential: Dict[str, Any] = Field(
        default=None,
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
        description="Credentials for the specified provider",
    )
    is_active: Optional[bool] = Field(
        default=None, description="Whether the credentials are active"
    )


class Credential(CredsBase, table=True):
    """Database model for storing provider credentials.
    Each row represents credentials for a single provider.
    """

    __table_args__ = (
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "provider",
            name="uq_credential_org_project_provider",
        ),
    )

    id: int = Field(default=None, primary_key=True)
    provider: str = Field(
        index=True, description="Provider name like 'openai', 'gemini'"
    )
    credential: str = Field(
        sa_column=sa.Column(sa.String, nullable=False),
        description="Encrypted provider-specific credentials",
    )
    inserted_at: datetime = Field(
        default_factory=now,
        sa_column=sa.Column(sa.DateTime, default=datetime.utcnow, nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=now,
        sa_column=sa.Column(sa.DateTime, onupdate=datetime.utcnow, nullable=False),
    )

    organization: Optional["Organization"] = Relationship(back_populates="creds")
    project: Optional["Project"] = Relationship(back_populates="creds")

    def to_public(self) -> "CredsPublic":
        """Convert the database model to a public model with decrypted credentials."""
        from app.core.security import decrypt_credentials

        return CredsPublic(
            id=self.id,
            organization_id=self.organization_id,
            project_id=self.project_id,
            is_active=self.is_active,
            provider=self.provider,
            credential=decrypt_credentials(self.credential)
            if self.credential
            else None,
            inserted_at=self.inserted_at,
            updated_at=self.updated_at,
        )


class CredsPublic(CredsBase):
    """Public representation of credentials, excluding sensitive information."""

    id: int
    provider: str
    credential: Optional[Dict[str, Any]] = None
    inserted_at: datetime
    updated_at: datetime
