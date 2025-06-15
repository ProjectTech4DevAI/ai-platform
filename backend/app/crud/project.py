from typing import List, Optional
from datetime import datetime, timezone
from sqlmodel import Session, select

from app.models import Project, ProjectCreate, Organization
from app.core.util import now


def create_project(*, session: Session, project_create: ProjectCreate) -> Project:
    db_project = Project.model_validate(project_create)
    db_project.inserted_at = now()
    db_project.updated_at = now()
    session.add(db_project)
    session.commit()
    session.refresh(db_project)
    return db_project


def get_project_by_id(*, session: Session, project_id: int) -> Optional[Project]:
    statement = select(Project).where(Project.id == project_id)
    return session.exec(statement).first()


def get_projects_by_organization(*, session: Session, org_id: int) -> List[Project]:
    statement = select(Project).where(Project.organization_id == org_id)
    return session.exec(statement).all()


def validate_project(session: Session, project_id: int) -> Project:
    """
    Ensures that an project exists and is active.
    """
    project = get_project_by_id(session=session, project_id=project_id)
    if not project:
        raise ValueError("Project not found")

    if not project.is_active:
        raise ValueError("Project is not active")

    return project
