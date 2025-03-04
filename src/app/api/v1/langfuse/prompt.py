from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.exceptions.http_exceptions import NotFoundException, ForbiddenException
from ....core.db.database import async_get_db
from ....core.utils.cache import cache
from ....schemas.langfuse.prompt import PromptQueryParams, PromptMetaListResponse, PromptDetailResponse, PromptCreateRequest
from ....services.langfuse import LangfuseClient
from ....schemas.user import UserRead
from ....api.dependencies import get_current_user


router = APIRouter(prefix="/{project_id}/langfuse",tags=["langfuse"])


async def validate_user_project_membership(db: AsyncSession, user_id: int, project_id: int) -> bool:
    """Mock function to validate if a user is part of a project. Replace with actual DB query later."""
    return True  # Change this to a real check when implementing

@router.post("/prompts", response_model=PromptDetailResponse)
async def create_prompt_version(
    request: Request,
    project_id: int,
    prompt_data: PromptCreateRequest,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> PromptDetailResponse:
    """Create a new version of a prompt within a project."""
    
    is_member = await validate_user_project_membership(db, current_user, project_id)
    if not is_member:
        raise ForbiddenException("You do not have access to this project.")

    # Ensure project_id is part of the tags for filtering
    prompt_data.tags.append(f"project-{project_id}")

    client = LangfuseClient()
    response = await client.create_prompt_version(prompt_data)

    return response

@router.get("/prompts", response_model=PromptMetaListResponse)
async def get_prompts(
    request: Request,
    project_id: int,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    query: Annotated[PromptQueryParams, Depends()],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> PromptMetaListResponse:
    """Fetch a list of prompt names with versions and labels using validated query params."""
    is_member = await validate_user_project_membership(db, current_user, project_id)
    if not is_member:
        raise ForbiddenException("You do not have access to this project.")
    
    # Append project_id as a tag for filtering
    if query.tag:
        query.tag = f"{query.tag},project-{project_id}"
    else:
        query.tag = f"project-{project_id}"

    client = LangfuseClient()
    response = await client.get_prompts(query)
    if not response:
        raise NotFoundException("No prompts found.")

    return response

@router.get("/prompt/{prompt_name}", response_model=PromptDetailResponse)
async def get_prompt(
    request: Request,
    project_id: int,
    prompt_name: str,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
    version: Optional[int] = None,
    label: Optional[str] = None,
) -> PromptDetailResponse:
    """Fetch a specific prompt by name, with optional version or label."""
    is_member = await validate_user_project_membership(db, current_user, project_id)
    if not is_member:
        raise ForbiddenException("You do not have access to this project.")

    client = LangfuseClient()
    response = await client.get_prompt(prompt_name, version, label)
    
    if not response:
        raise NotFoundException("Prompt not found.")

    return response