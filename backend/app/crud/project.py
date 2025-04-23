from typing import List, Optional
from datetime import datetime

from sqlmodel import Session, select

from app.models import Project, ProjectCreate, ProjectUpdate


def create_project(*, session: Session, project_create: ProjectCreate) -> Project:
    db_project = Project.model_validate(project_create)
    # Set timestamps
    db_project.inserted_at = datetime.utcnow()
    db_project.updated_at = datetime.utcnow()
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


def update_project(
    *, session: Session, project: Project, project_in: ProjectUpdate
) -> Project:
    project_data = project_in.model_dump(exclude_unset=True)
    for key, value in project_data.items():
        setattr(project, key, value)
    # Update the updated_at timestamp
    project.updated_at = datetime.utcnow()
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def delete_project(*, session: Session, project: Project) -> Project:
    project.is_deleted = True
    project.deleted_at = datetime.utcnow()
    project.updated_at = datetime.utcnow()
    session.add(project)
    session.commit()
    session.refresh(project)
    return project
