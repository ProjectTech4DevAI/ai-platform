from typing import List, Optional
from sqlmodel import Session, select
from app.models import Project, ProjectCreate


# Create a new project linked to an organization
def create_project(*, session: Session, project_create: ProjectCreate, org_id: int) -> Project:
    db_project = Project.model_validate(project_create, update={"organization_id": org_id})
    session.add(db_project)
    session.commit()
    session.refresh(db_project)
    return db_project


# Get project by ID
def get_project_by_id(*, session: Session, project_id: int) -> Optional[Project]:
    statement = select(Project).where(Project.id == project_id)
    return session.exec(statement).first()


# Get all projects for a specific organization
def get_projects_by_organization(*, session: Session, org_id: int) -> List[Project]:
    statement = select(Project).where(Project.organization_id == org_id)
    return session.exec(statement).all()
