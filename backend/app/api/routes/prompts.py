import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from sqlmodel import Session

from app.api.deps import CurrentUserOrgProject, get_db
from app.crud import (
    create_prompt,
    delete_prompt,
    get_prompt_by_id,
    get_prompts,
    count_prompts_in_project,
    update_prompt,
)
from app.models import (
    PromptCreate,
    PromptPublic,
    PromptUpdate,
    PromptWithVersion,
    PromptWithVersions,
)
from app.utils import APIResponse


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prompts", tags=["Prompts"])


@router.post("/", response_model=APIResponse[PromptWithVersion], status_code=201)
def create_prompt_route(
    prompt_in: PromptCreate,
    current_user: CurrentUserOrgProject,
    session: Session = Depends(get_db),
):
    """
    Create a new prompt under the specified organization and project.
    """
    prompt, version = create_prompt(
        session=session, prompt_in=prompt_in, project_id=current_user.project_id
    )
    prompt_with_version = PromptWithVersion(**prompt.model_dump(), version=version)
    return APIResponse.success_response(prompt_with_version)


@router.get(
    "/",
    response_model=APIResponse[list[PromptPublic]],
)
def get_prompts_route(
    current_user: CurrentUserOrgProject,
    skip: int = Query(
        0, ge=0, description="Number of prompts to skip (for pagination)."
    ),
    limit: int = Query(100, gt=0, description="Maximum number of prompts to return."),
    session: Session = Depends(get_db),
):
    """
    Get all prompts for the specified organization and project.
    """
    prompts = get_prompts(
        session=session,
        project_id=current_user.project_id,
        skip=skip,
        limit=limit,
    )
    total = count_prompts_in_project(
        session=session, project_id=current_user.project_id
    )
    metadata = {"pagination": {"total": total, "skip": skip, "limit": limit}}
    return APIResponse.success_response(prompts, metadata=metadata)


@router.get(
    "/{prompt_id}",
    response_model=APIResponse[PromptWithVersions],
    summary="Get a single prompt by its ID by default returns the active version",
)
def get_prompt_by_id_route(
    current_user: CurrentUserOrgProject,
    prompt_id: UUID = Path(..., description="The ID of the prompt to fetch"),
    include_versions: bool = Query(
        False, description="Whether to include all versions of the prompt."
    ),
    session: Session = Depends(get_db),
):
    """
    Get a single prompt by its ID.
    """
    prompt, versions = get_prompt_by_id(
        session=session,
        prompt_id=prompt_id,
        project_id=current_user.project_id,
        include_versions=include_versions,
    )
    prompt_with_versions = PromptWithVersions(**prompt.model_dump(), versions=versions)
    return APIResponse.success_response(prompt_with_versions)


@router.patch("/{prompt_id}", response_model=APIResponse[PromptPublic])
def update_prompt_route(
    current_user: CurrentUserOrgProject,
    prompt_update: PromptUpdate,
    prompt_id: UUID = Path(..., description="The ID of the prompt to Update"),
    session: Session = Depends(get_db),
):
    """
    Update a prompt's name or description.
    """

    prompt = update_prompt(
        session=session,
        prompt_id=prompt_id,
        project_id=current_user.project_id,
        prompt_update=prompt_update,
    )
    return APIResponse.success_response(prompt)


@router.delete("/{prompt_id}", response_model=APIResponse)
def delete_prompt_route(
    current_user: CurrentUserOrgProject,
    prompt_id: UUID = Path(..., description="The ID of the prompt to delete"),
    session: Session = Depends(get_db),
):
    """
    Delete a prompt by ID.
    """
    delete_prompt(
        session=session, prompt_id=prompt_id, project_id=current_user.project_id
    )
    return APIResponse.success_response(
        data={"message": "Prompt deleted successfully."}
    )
