from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db.database import Base


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)
    name: Mapped[str] = mapped_column(String(20), nullable=False, index=True, unique=True)
    color: Mapped[str] = mapped_column(String(7), nullable=False) # Hex color format (#RRGGBB)

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default_factory=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, onupdate=lambda: datetime.now(UTC))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    is_deleted: Mapped[bool] = mapped_column(default=False, index=True)
    
    prompt_tags = relationship("PromptTag", back_populates="tag", cascade="all, delete-orphan")
