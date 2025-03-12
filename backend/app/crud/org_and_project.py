from typing import Any
from sqlmodel import Session, select
from models import Organization, OrganizationCreate, Project, ProjectCreate


# Create a new organization
def create_organization(*, session: Session, org_create: OrganizationCreate) -> Organization:
    db_org = Organization.model_validate(org_create)
    session.add(db_org)
    session.commit()
    session.refresh(db_org)
    return db_org


# Get organization by ID
def get_organization_by_id(*, session: Session, org_id: int) -> Organization | None:
    statement = select(Organization).where(Organization.id == org_id)
    return session.exec(statement).first()


# Create a new project linked to an organization
def create_project(*, session: Session, project_create: ProjectCreate, org_id: int) -> Project:
    db_project = Project.model_validate(project_create, update={"organization_id": org_id})
    session.add(db_project)
    session.commit()
    session.refresh(db_project)
    return db_project


# Get project by ID
def get_project_by_id(*, session: Session, project_id: int) -> Project | None:
    statement = select(Project).where(Project.id == project_id)
    return session.exec(statement).first()


# Get all projects for a specific organization
def get_projects_by_organization(*, session: Session, org_id: int) -> list[Project]:
    statement = select(Project).where(Project.organization_id == org_id)
    return session.exec(statement).all()
