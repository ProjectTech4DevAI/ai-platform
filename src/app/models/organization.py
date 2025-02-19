import uuid

from sqlalchemy import Column, String, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..core.db.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)

    # Relationships
    projects = relationship("Project", back_populates="organization", cascade="all, delete-orphan")
    credentials = relationship(
        "Credentials", back_populates="organization", cascade="all, delete-orphan"
    )
