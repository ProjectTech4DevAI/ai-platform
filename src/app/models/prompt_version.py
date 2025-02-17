from datetime import UTC, datetime
from sqlalchemy import DateTime, ForeignKey, Text, Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.db.database import Base


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, nullable=False, unique=True, init=False)
    prompt_id: Mapped[int] = mapped_column(ForeignKey("prompts.id"), nullable=False, index=True)
    
    template: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default_factory=lambda: datetime.now(UTC))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    prompt = relationship("Prompt", back_populates="versions")
    
    __table_args__ = (
        UniqueConstraint("prompt_id", "version", name="uq_prompt_version"),
    )
