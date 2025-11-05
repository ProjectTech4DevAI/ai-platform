from uuid import UUID, uuid4
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlmodel import Field, SQLModel, UniqueConstraint

from app.core.util import now


class ConfigBase(SQLModel):
    """Base model for LLM configuration metadata"""

    name: str = Field(index=True, min_length=1, max_length=128, description="Config name")
    description: str | None = Field(default=None, max_length=512, description="Optional description")


class Config(ConfigBase, table=True):
    """Database model for LLM configuration storage"""

    __tablename__ = "config"
    __table_args__ = (
        UniqueConstraint(
            "name",
            "project_id",
        ),
    )

    id: UUID = Field(default=uuid4, primary_key=True)

    project_id: int = Field(
        foreign_key="project.id",
        index=True,
        nullable=False,
        ondelete="CASCADE",
    )

    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)

    deleted_at: datetime | None = Field(default=None, nullable=True)


class ConfigCreate(SQLModel):
    """Create new configuration"""

    name: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=500)

    # Initial version data
    config_json: dict[str, Any] = Field(description="Provider-specific parameters")
    commit_message: str | None = Field(
        default=None,
        max_length=512,
        description="Optional message describing the changes in this version",
    )



class ConfigUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=512, description="Optional description")


class ConfigPublic(ConfigBase):

    id: int
    project_id: int
    organization_id: int
    latest_version_id: int | None
    created_by_user_id: int | None
    inserted_at: datetime
    updated_at: datetime
