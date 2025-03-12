from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select
from typing import Any

from ...models import (
    Organization,
    Project,
    OrganizationCreate,
    OrganizationUpdate,
    ProjectCreate,
    ProjectUpdate,
    OrganizationPublic,
    ProjectPublic,
)
from ..deps import get_current_active_superuser, SessionDep

router = APIRouter(prefix="/organization", tags=["organization_project"])


# Retrieve organizations
@router.get("/organizations", response_model=list[OrganizationPublic])
def read_organizations(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    count_statement = select(func.count()).select_from(Organization)
    count = session.exec(count_statement).one()

    statement = select(Organization).offset(skip).limit(limit)
    organizations = session.exec(statement).all()

    return organizations


# Create a new organization
@router.post("/organizations", response_model=OrganizationPublic)
def create_organization(*, session: SessionDep, org_in: OrganizationCreate) -> Any:
    org = Organization.model_validate(org_in)
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


# Update an organization
@router.patch("/organizations/{org_id}", response_model=OrganizationPublic)
def update_organization(*, session: SessionDep, org_id: int, org_in: OrganizationUpdate) -> Any:
    org = session.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    org_data = org_in.model_dump(exclude_unset=True)
    for key, value in org_data.items():
        setattr(org, key, value)
    
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


# Delete an organization
@router.delete("/organizations/{org_id}")
def delete_organization(session: SessionDep, org_id: int) -> None:
    org = session.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    session.delete(org)
    session.commit()


# Retrieve projects
@router.get("/projects", response_model=list[ProjectPublic])
def read_projects(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    count_statement = select(func.count()).select_from(Project)
    count = session.exec(count_statement).one()

    statement = select(Project).offset(skip).limit(limit)
    projects = session.exec(statement).all()

    return projects


# Create a new project
@router.post("/projects", response_model=ProjectPublic)
def create_project(*, session: SessionDep, project_in: ProjectCreate) -> Any:
    project = Project.model_validate(project_in)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


# Update a project
@router.patch("/projects/{project_id}", response_model=ProjectPublic)
def update_project(*, session: SessionDep, project_id: int, project_in: ProjectUpdate) -> Any:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_data = project_in.model_dump(exclude_unset=True)
    for key, value in project_data.items():
        setattr(project, key, value)
    
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


# Delete a project
@router.delete("/projects/{project_id}")
def delete_project(session: SessionDep, project_id: int) -> None:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    session.delete(project)
    session.commit()