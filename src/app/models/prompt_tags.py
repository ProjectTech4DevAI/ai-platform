from datetime import UTC, datetime
from sqlalchemy import DateTime, ForeignKey, String, Text, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db.database import Base


class PromptTag(Base):
    __tablename__ = "prompt_tags"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)
    prompt_id: Mapped[int] = mapped_column(ForeignKey("prompts.id"), nullable=False, index=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), nullable=False, index=True)

    prompt = relationship("Prompt", back_populates="tags")
    tag = relationship("Tag", back_populates="prompt_tags")
    