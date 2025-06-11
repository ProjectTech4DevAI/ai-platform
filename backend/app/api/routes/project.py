from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import (
    Project,
    ProjectCreate,
    ProjectUpdate,
    ProjectPublic,
    Organization,
)
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from app.crud.project import (
    create_project,
    get_project_by_id,
    get_projects_by_organization,
)
from app.utils import APIResponse
from app.core.exception_handlers import NotFoundException

router = APIRouter(prefix="/projects", tags=["projects"])


# Retrieve projects


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[List[ProjectPublic]],
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


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[ProjectPublic],
)
def create_new_project(*, session: SessionDep, project_in: ProjectCreate):
    organization = session.get(Organization, project_in.organization_id)
    if not organization:
        raise NotFoundException("Organization not found")
    project = create_project(session=session, project_create=project_in)
    return APIResponse.success_response(project)


@router.get(
    "/{project_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[ProjectPublic],
)
def read_project(*, session: SessionDep, project_id: int):
    project = get_project_by_id(session=session, project_id=project_id)
    if project is None:
        raise NotFoundException("Project not found")
    return APIResponse.success_response(project)


@router.patch(
    "/{project_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[ProjectPublic],
)
def update_project(*, session: SessionDep, project_id: int, project_in: ProjectUpdate):
    project = get_project_by_id(session=session, project_id=project_id)
    if project is None:
        raise NotFoundException("Project not found")

    project_data = project_in.model_dump(exclude_unset=True)
    project = project.model_copy(update=project_data)

    session.add(project)
    session.commit()
    session.flush()
    return APIResponse.success_response(project)


@router.delete(
    "/{project_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[None],
)
def delete_project(session: SessionDep, project_id: int):
    project = get_project_by_id(session=session, project_id=project_id)
    if project is None:
        raise NotFoundException("Project not found")

    session.delete(project)
    session.commit()

    return APIResponse.success_response(None)
