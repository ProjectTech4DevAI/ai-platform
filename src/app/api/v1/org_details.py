from typing import Annotated, Any
import logging

from fastapi import APIRouter, Depends, Request, HTTPException
from fastcrud.paginated import PaginatedListResponse, compute_offset, paginated_response
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import (
    DuplicateValueException,
    NotFoundException,
)
from ...crud.crud_org import crud_organizations
from ...crud.crud_projects import crud_projects
from ...schemas.organization import (
    OrganizationCreateInternal,
    OrganizationRead,
    OrganizationUpdate,
    OrganizationCreate
)
from ...schemas.project import ProjectCreateInternal, ProjectRead, ProjectUpdate

router = APIRouter(tags=["organizations"])


@router.post("/organization", response_model=OrganizationRead, status_code=201)
async def create_or_get_organization(
    request: Request,
    organization_name: OrganizationCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> OrganizationRead:
    # Checking if organization exists
    try:
        # Convert OrganizationCreate model to dictionary
        org_internal_dict = organization_name.model_dump()

        # Check if organization exists
        org_row = await crud_organizations.get(
            db=db, name=organization_name.name, schema_to_select=OrganizationRead
        )
        
        if org_row:
            return org_row  # Return existing organization

        # Create new organization
        org_internal = OrganizationCreateInternal(name=organization_name.name)
        created_org = await crud_organizations.create(db=db, object=org_internal)

        return created_org

    except Exception as e:
        logging.error(f"Error in create_or_get_organization: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

# 🚀 List Organizations (Paginated)
@router.get("/organizations", response_model=PaginatedListResponse[OrganizationRead])
async def list_organizations(
    request: Request,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    page: int = 1,
    items_per_page: int = 10,
) -> dict:
    orgs_data = await crud_organizations.get_multi(
        db=db,
        offset=compute_offset(page, items_per_page),
        limit=items_per_page,
        schema_to_select=OrganizationRead,
    )

    response: dict[str, Any] = paginated_response(
        crud_data=orgs_data, page=page, items_per_page=items_per_page
    )
    return response


# 🚀 Update an Organization
@router.patch("/organization/{organization_id}")
async def update_organization(
    request: Request,
    organization_id: int,
    values: OrganizationUpdate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, str]:
    org_row = await crud_organizations.get(
        db=db, id=organization_id, schema_to_select=OrganizationRead
    )
    if org_row is None:
        raise NotFoundException("Organization not found")

    await crud_organizations.update(db=db, object=values, id=organization_id)
    return {"message": "Organization updated"}


# 🚀 Assign a Project to an Organization (or Use Default)
@router.post("/project", response_model=ProjectRead, status_code=201)
async def create_or_get_project(
    request: Request,
    organization_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    project_name: str | None = None,
) -> ProjectRead:
    # Ensure organization exists
    org_row = await crud_organizations.get(
        db=db, id=organization_id, schema_to_select=OrganizationRead
    )
    if not org_row:
        raise NotFoundException("Organization not found")

    # Assign or create project
    project_name = project_name if project_name else "Default Project"
    project_row = await crud_projects.get(
        db=db,
        name=project_name,
        organization_id=organization_id,
        schema_to_select=ProjectRead,
    )

    if project_row:
        return project_row

    # Create new project
    project_internal = ProjectCreateInternal(
        name=project_name, organization_id=organization_id
    )
    created_project: ProjectRead = await crud_projects.create(
        db=db, object=project_internal
    )
    return created_project


# 🚀 List Projects for an Organization (Paginated)
@router.get("/projects", response_model=PaginatedListResponse[ProjectRead])
async def list_projects(
    request: Request,
    organization_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    page: int = 1,
    items_per_page: int = 10,
) -> dict:
    projects_data = await crud_projects.get_multi(
        db=db,
        offset=compute_offset(page, items_per_page),
        limit=items_per_page,
        schema_to_select=ProjectRead,
        organization_id=organization_id,
    )

    response: dict[str, Any] = paginated_response(
        crud_data=projects_data, page=page, items_per_page=items_per_page
    )
    return response


# 🚀 Update a Project
@router.patch("/project/{project_id}")
async def update_project(
    request: Request,
    project_id: int,
    values: ProjectUpdate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, str]:
    project_row = await crud_projects.get(
        db=db, id=project_id, schema_to_select=ProjectRead
    )
    if project_row is None:
        raise NotFoundException("Project not found")

    await crud_projects.update(db=db, object=values, id=project_id)
    return {"message": "Project updated"}


# 🚀 Delete an Organization
@router.delete("/organization/{organization_id}")
async def delete_organization(
    request: Request,
    organization_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, str]:
    org_row = await crud_organizations.get(
        db=db, id=organization_id, schema_to_select=OrganizationRead
    )
    if not org_row:
        raise NotFoundException("Organization not found")

    await crud_organizations.delete(db=db, id=organization_id)
    return {"message": "Organization deleted"}


# 🚀 Delete a Project
@router.delete("/project/{project_id}")
async def delete_project(
    request: Request,
    project_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, str]:
    project_row = await crud_projects.get(
        db=db, id=project_id, schema_to_select=ProjectRead
    )
    if not project_row:
        raise NotFoundException("Project not found")

    await crud_projects.delete(db=db, id=project_id)
    return {"message": "Project deleted"}
