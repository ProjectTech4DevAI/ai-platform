from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import select

from app.api.deps import (
    SessionDep,
    get_current_active_superuser,
)
from app.crud.project import create_project, get_project_by_id
from app.models import Project, ProjectCreate, ProjectPublic, ProjectUpdate
from app.utils import APIResponse

router = APIRouter(prefix="/projects", tags=["projects"])


# Retrieve projects
@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[list[ProjectPublic]],
)
def read_projects(
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    count_statement = select(func.count()).select_from(Project)
    count = session.exec(count_statement).one()

    statement = select(Project).offset(skip).limit(limit)
    projects = session.exec(statement).all()

    return APIResponse.success_response(projects)


# Create a new project
@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[ProjectPublic],
)
def create_new_project(*, session: SessionDep, project_in: ProjectCreate):
    project = create_project(session=session, project_create=project_in)
    return APIResponse.success_response(project)


@router.get(
    "/{project_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[ProjectPublic],
)
def read_project(*, session: SessionDep, project_id: int):
    """
    Retrieve a project by ID.
    """
    project = get_project_by_id(session=session, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return APIResponse.success_response(project)


# Update a project
@router.patch(
    "/{project_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[ProjectPublic],
)
def update_project(*, session: SessionDep, project_id: int, project_in: ProjectUpdate):
    project = get_project_by_id(session=session, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    project_data = project_in.model_dump(exclude_unset=True)
    project = project.model_copy(update=project_data)

    session.add(project)
    session.commit()
    session.flush()
    return APIResponse.success_response(project)


# Delete a project
@router.delete("/{project_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_project(session: SessionDep, project_id: int):
    project = get_project_by_id(session=session, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    session.delete(project)
    session.commit()

    return APIResponse.success_response(None)
