from uuid import UUID, uuid4
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlmodel import Field, SQLModel, UniqueConstraint
from pydantic import field_validator

from app.core.util import now
from .version import ConfigVersionPublic


class ConfigBase(SQLModel):
    """Base model for LLM configuration metadata"""

    name: str = Field(
        index=True, min_length=1, max_length=128, description="Config name"
    )
    description: str | None = Field(
        default=None, max_length=512, description="Optional description"
    )


class Config(ConfigBase, table=True):
    """Database model for LLM configuration storage"""

    __tablename__ = "config"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "name",
            "deleted_at",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    project_id: int = Field(
        foreign_key="project.id",
        index=True,
        nullable=False,
        ondelete="CASCADE",
    )

    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)

    deleted_at: datetime | None = Field(default=None, nullable=True)


class ConfigCreate(ConfigBase):
    """Create new configuration"""

    # Initial version data
    config_blob: dict[str, Any] = Field(description="Provider-specific parameters")
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


class ConfigUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(
        default=None, max_length=512, description="Optional description"
    )


class ConfigPublic(ConfigBase):
    id: UUID
    project_id: int
    inserted_at: datetime
    updated_at: datetime


class ConfigWithVersion(ConfigPublic):
    version: ConfigVersionPublic


class ConfigWithVersions(ConfigPublic):
    versions: list[ConfigVersionPublic]
