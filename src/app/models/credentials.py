import uuid

from sqlalchemy import Column, String, ForeignKey, JSON, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime

from ..core.db.database import Base


class Credentials(Base):
    __tablename__ = "credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    token = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    secrets = Column(JSON)
    email = Column(String, nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="credentials")
    project = relationship("Project", back_populates="credentials")
