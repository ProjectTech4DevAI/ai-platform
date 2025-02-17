from datetime import UTC, datetime
from sqlalchemy import DateTime, ForeignKey, String, Boolean, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.db.database import Base


class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, nullable=False, unique=True, init=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)

    active_version: Mapped[str] = mapped_column(String(50), nullable=False)
    is_suggested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default_factory=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, onupdate=lambda: datetime.now(UTC))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    versions = relationship("PromptVersion", back_populates="prompt", cascade="all, delete-orphan")
    tags = relationship("PromptTag", back_populates="prompt", cascade="all, delete-orphan")
