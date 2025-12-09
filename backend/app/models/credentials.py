from typing import Dict, Any, Optional
import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel
from datetime import datetime

from app.core.util import now


class CredsBase(SQLModel):
    organization_id: int = Field(
        sa_column=sa.Column(
            sa.Integer,
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
            comment="Reference to the organization",
        )
    )
    project_id: int = Field(
        sa_column=sa.Column(
            sa.Integer,
            sa.ForeignKey("project.id", ondelete="CASCADE"),
            nullable=False,
            comment="Reference to the project",
        )
    )
    is_active: bool = Field(
        default=True,
        sa_column=sa.Column(
            sa.Boolean,
            default=True,
            nullable=False,
            comment="Flag indicating if this credential is currently active and usable",
        ),
    )


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

    id: int = Field(
        default=None,
        sa_column=sa.Column(
            sa.Integer,
            primary_key=True,
            comment="Unique ID for the credential",
        ),
    )
    provider: str = Field(
        sa_column=sa.Column(
            sa.String,
            index=True,
            nullable=False,
            comment="Provider name like 'openai', 'gemini'",
        ),
        description="Provider name like 'openai', 'gemini'",
    )
    credential: str = Field(
        sa_column=sa.Column(
            sa.String,
            nullable=False,
            comment="Encrypted JSON string containing provider-specific API credentials",
        ),
        description="Encrypted JSON string containing provider-specific API credentials",
    )
    inserted_at: datetime = Field(
        default_factory=now,
        sa_column=sa.Column(
            sa.DateTime,
            default=datetime.utcnow,
            nullable=False,
            comment="Timestamp when the credential was created",
        ),
    )
    updated_at: datetime = Field(
        default_factory=now,
        sa_column=sa.Column(
            sa.DateTime,
            onupdate=datetime.utcnow,
            nullable=False,
            comment="Timestamp when the credential was last updated",
        ),
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
