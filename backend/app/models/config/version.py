from datetime import datetime
from uuid import UUID, uuid4
from typing import Any

from pydantic import field_validator
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON
from sqlmodel import Field, SQLModel, UniqueConstraint

from app.core.util import now


class ConfigVersionBase(SQLModel):
    config_blob: dict[str, Any] = Field(
        sa_column=sa.Column(JSON, nullable=False),
        description="Provider-specific configuration parameters (temperature, max_tokens, etc.)",
    )
    commit_message: str | None = Field(
        default=None,
        max_length=512,
        description="Optional message describing the changes in this version",
    )

    @field_validator("config_blob")
    def validate_blob_not_empty(cls, value):
        if not value:
            raise ValueError("config_blob cannot be empty")
        return value


class ConfigVersion(ConfigVersionBase, table=True):
    __tablename__ = "config_version"
    __table_args__ = (
        UniqueConstraint(
            "config_id",
            "version",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    config_id: UUID = Field(
        foreign_key="config.id",
        index=True,
        nullable=False,
        ondelete="CASCADE",
    )
    version: int = Field(
        nullable=False, description="Version number starting at 1", ge=1
    )

    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)

    deleted_at: datetime | None = Field(default=None, nullable=True)


class ConfigVersionCreate(ConfigVersionBase):
    pass


class ConfigVersionPublic(ConfigVersionBase):
    id: UUID = Field(description="Unique id for the configuration version")
    config_id: UUID = Field(description="Id of the parent configuration")
    version: int = Field(nullable=False, description="Version number starting at 1")
    inserted_at: datetime
    updated_at: datetime


class ConfigVersionItems(SQLModel):
    """Lightweight version for lists (without large config_blob)"""

    id: UUID = Field(description="Unique id for the configuration version")
    version: int = Field(nullable=False, description="Version number starting at 1")
    config_id: UUID = Field(description="Id of the parent configuration")
    commit_message: str | None = Field(
        default=None,
        max_length=512,
        description="Optional message describing the changes in this version",
    )
    inserted_at: datetime
    updated_at: datetime
