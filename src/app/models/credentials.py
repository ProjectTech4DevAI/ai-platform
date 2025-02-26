import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, String, ForeignKey, JSON, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import EmailStr

from ..core.db.database import Base


class Credentials(Base):
    __tablename__ = "credentials"

    id: Mapped[int] = mapped_column(
        "id",
        autoincrement=True,
        nullable=False,
        unique=True,
        primary_key=True,
        init=False,
    )
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    secrets: Mapped[dict] = mapped_column(JSON)
    email: Mapped[EmailStr] = mapped_column(String(255), nullable=False)
    token: Mapped[str] = mapped_column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default_factory=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Relationships
    organization = relationship("Organization", back_populates="credentials")
    project = relationship("Project", back_populates="credentials")
