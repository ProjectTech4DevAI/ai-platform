from sqlalchemy import Column, String, ForeignKey, JSON, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from ..core.db.database import Base
  # Importing the Base from database setup

# Organization Table
class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization = Column(String, nullable=False, unique=True)

# Project Table
class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project = Column(String, nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))

    organization = relationship("Organization", back_populates="projects")

# Credentials Table
class Credentials(Base):
    __tablename__ = "credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    token = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    creation = Column(DateTime, default=datetime.utcnow)
    secrets = Column(JSON)

    organization = relationship("Organization", back_populates="credentials")
    project = relationship("Project", back_populates="credentials")

# Relationships
Organization.projects = relationship("Project", back_populates="organization")
Organization.credentials = relationship("Credentials", back_populates="organization")
Project.credentials = relationship("Credentials", back_populates="project")
