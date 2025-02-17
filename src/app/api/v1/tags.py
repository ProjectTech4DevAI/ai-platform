from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastcrud.paginated import PaginatedListResponse, compute_offset, paginated_response
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.dependencies import get_current_user, get_current_superuser, get_current_project, get_current_organization
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import ForbiddenException, NotFoundException
from ...core.utils.cache import cache
from ...crud.crud_tags import crud_tags
from ...crud.crud_users import crud_users
from ...schemas.tag import TagCreate, TagCreateInternal, TagRead, TagUpdate
from ...schemas.user import UserRead
from ...schemas.placeholder import ProjectRead, OrganizationRead #Remove once org and project gets setup

router = APIRouter(tags=["tags"])


async def validate_project_and_user_org_membership(
    db: AsyncSession,
    project_id: ProjectRead,
    organization_id: OrganizationRead,
    user: UserRead,
) -> None:
    """
    Once org and project are setup check for the following:
    - If the user is part of the project.
    - If the project belongs to the given organization.
    - Valid organization ID.
    - Valid project ID.
    """
    pass


async def validate_project_and_user_membership(
    db: AsyncSession,
    project_id: ProjectRead,
    user: UserRead,
) -> None:
    """
    Once project are setup check for the following:
    - If the user is part of the project, unauthorized user should not get access
    """
    pass


@router.post("/tag", response_model=TagRead, status_code=201)
async def create_tag(
    request: Request,
    tag: TagCreate,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    current_project: Annotated[ProjectRead, Depends(get_current_project)],
    current_org: Annotated[OrganizationRead, Depends(get_current_organization)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> TagRead:
    """Create a new tag scoped to a project."""
    await validate_project_and_user_org_membership(db, current_project, current_org, current_user)

    tag_internal_dict = tag.model_dump()
    tag_internal_dict["project_id"] = current_project['id']
    tag_internal_dict["organization_id"] = current_org['id']

    tag_internal = TagCreateInternal(**tag_internal_dict)
    created_tag: TagRead = await crud_tags.create(db=db, object=tag_internal)
    return created_tag


@router.get("/tags", response_model=PaginatedListResponse[TagRead])
async def read_tags(
    request: Request,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    current_project: Annotated[ProjectRead, Depends(get_current_project)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
    page: int = 1,
    items_per_page: int = 10,
) -> dict:
    """Retrieve all tags associated with the given project"""
    # Validate if user is part of project or not
    await validate_project_and_user_membership(db, current_project, current_user)
    
    tags_data = await crud_tags.get_multi(
        db=db,
        offset=compute_offset(page, items_per_page),
        limit=items_per_page,
        schema_to_select=TagRead,
        project_id=current_project["id"],
        is_deleted=False,
    )

    response: dict[str, Any] = paginated_response(crud_data=tags_data, page=page, items_per_page=items_per_page)
    return response


@router.get("/tag/{tag_id}", response_model=TagRead)
async def read_tag(
    request: Request, 
    tag_id: int,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    current_project: Annotated[ProjectRead, Depends(get_current_project)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> TagRead:
    """Retrieve a single tag by its ID, ensuring it belongs to the given project and organization."""
    # Validate if user is part of project or not
    await validate_project_and_user_membership(db, current_project, current_user)
    
    db_tag = await crud_tags.get(
        db=db, schema_to_select=TagRead,
        id=tag_id,
        project_id=current_project["id"],
        is_deleted=False
    )

    if db_tag is None:
        raise NotFoundException("Tag not found")

    return db_tag


@router.patch("/tag/{tag_id}")
async def patch_tag(
    request: Request,
    tag_id: int,
    values: TagUpdate,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    current_project: Annotated[ProjectRead, Depends(get_current_project)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, str]:
    """Update a tag if it exists and belongs to the given project and organization."""
    # Validate if user is part of project or not
    await validate_project_and_user_membership(db, current_project, current_user)

    db_tag = await crud_tags.get(
        db=db,
        schema_to_select=TagRead,
        id=tag_id,
        project_id=current_project["id"],
        is_deleted=False
    )

    if db_tag is None:
        raise NotFoundException("Tag not found")

    await crud_tags.update(db=db, object=values, id=tag_id)
    return {"message": "Tag updated successfully"}


@router.delete("/tag/{tag_id}")
async def erase_tag(
    request: Request,
    tag_id: int,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    current_project: Annotated[ProjectRead, Depends(get_current_project)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, str]:
    """Soft delete a tag by ID if it belongs to the given project and organization."""
    # Validate if user is part of project or not
    await validate_project_and_user_membership(db, current_project, current_user)
    
    db_tag = await crud_tags.get(
        db=db,
        schema_to_select=TagRead,
        id=tag_id,
        project_id=current_project["id"],
        is_deleted=False
    )

    if db_tag is None:
        raise NotFoundException("Tag not found")

    await crud_tags.delete(db=db, id=tag_id)
    return {"message": "Tag deleted successfully"}


@router.delete("/db_tag/{tag_id}", dependencies=[Depends(get_current_superuser)])
async def erase_db_tag(
    request: Request,
    tag_id: int,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    current_project: Annotated[ProjectRead, Depends(get_current_project)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, str]:
    """Soft delete a tag by ID if it belongs to the given project and organization."""
    db_tag = await crud_tags.get(
        db=db,
        schema_to_select=TagRead,
        id=tag_id,
        project_id=current_project["id"],
        is_deleted=False
    )

    if db_tag is None:
        raise NotFoundException("Tag not found")

    await crud_tags.db_delete(db=db, id=tag_id)
    return {"message": "Tag deleted successfully"}