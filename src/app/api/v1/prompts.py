from typing import Annotated, Any
from fastapi import APIRouter, Depends, Request
from fastcrud.paginated import PaginatedListResponse, compute_offset, paginated_response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from ...api.dependencies import get_current_user, get_current_project, get_current_organization
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import ForbiddenException, NotFoundException
from ...crud.crud_prompts import crud_prompts
from ...crud.crud_prompt_versions import crud_prompt_versions
from ...schemas.prompt import PromptCreate, PromptRead, PromptCreate, PromptCreateInternal
from ...schemas.prompt_version import PromptVersionRead, PromptVersionCreate, PromptVersionCreateInternal
from ...schemas.placeholder import ProjectRead, OrganizationRead  # Remove once org and project gets setup
from ...schemas.user import UserRead

router = APIRouter(tags=["prompts"])

async def validate_project_and_user_org_membership(
    db: AsyncSession,
    project_id: ProjectRead,
    organization_id: OrganizationRead,
    user: UserRead,
) -> None:
    """
    Ensure user is part of the project and that the project belongs to the given organization.
    """
    # Placeholder logic for validation
    pass

async def validate_project_and_user_membership(
    db: AsyncSession,
    project_id: ProjectRead,
    user: UserRead,
) -> None:
    """
    Ensure user is part of the project.
    """
    # Placeholder logic for validation
    pass


@router.post("/prompt", response_model=PromptRead, status_code=201)
async def create_prompt(
    request: Request,
    prompt: PromptCreate,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    current_project: Annotated[ProjectRead, Depends(get_current_project)],
    current_org: Annotated[OrganizationRead, Depends(get_current_organization)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> PromptRead:
    """Create a new prompt scoped to a project."""
    # Validate user and project membership
    await validate_project_and_user_org_membership(db, current_project, current_org, current_user)
    

    prompt_internal_dict = prompt.model_dump()
    prompt_internal_dict.update({
        "project_id": current_project["id"],
        "organization_id": current_org["id"]
    })
    
    # Extract and remove template before creating the prompt
    prompt_template = prompt_internal_dict.pop("template", None)
    
    # Create the prompt
    created_prompt = await crud_prompts.create(db=db, object=PromptCreateInternal(**prompt_internal_dict))
    
    # Create the initial version for the prompt
    created_version = PromptVersionCreateInternal(
        prompt_id=created_prompt.id,
        version=prompt_internal_dict["active_version"],
        template=prompt_template,
    )
    
    await crud_prompt_versions.create(db=db, object=created_version)
    

    return PromptRead(
        id=created_prompt.id,
        title=created_prompt.title,
        active_version=created_version.version,
        template=created_version.template,
        created_at=created_prompt.created_at,
        updated_at=created_prompt.updated_at,
    )
