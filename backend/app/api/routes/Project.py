from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select
from typing import Any, List

from app.models import Project, ProjectCreate, ProjectUpdate, ProjectPublic
from app.api.deps import SessionDep
from app.crud.project import create_project, get_project_by_id, get_projects_by_organization

router = APIRouter(prefix="/projects", tags=["projects"])


# Retrieve projects
@router.get("/", response_model=List[ProjectPublic])
def read_projects(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    count_statement = select(func.count()).select_from(Project)
    count = session.exec(count_statement).one()

    statement = select(Project).offset(skip).limit(limit)
    projects = session.exec(statement).all()

    return projects


# Create a new project
@router.post("/", response_model=ProjectPublic)
def create_new_project(*, session: SessionDep, project_in: ProjectCreate, org_id: int) -> Any:
    return create_project(session=session, project_create=project_in, org_id=org_id)


# Update a project
@router.patch("/{project_id}", response_model=ProjectPublic)
def update_project(*, session: SessionDep, project_id: int, project_in: ProjectUpdate) -> Any:
    project = get_project_by_id(session=session, project_id=project_id)
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
@router.delete("/{project_id}")
def delete_project(session: SessionDep, project_id: int) -> None:
    project = get_project_by_id(session=session, project_id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    session.delete(project)
    session.commit()
