import logging

from fastapi import APIRouter, Depends, Path, Query
from sqlmodel import Session

from app.api.deps import get_db, get_current_user_org_project
from app.core.exception_handlers import HTTPException
from app.crud import (
    count_prompts_by_project,
    create_prompt,
    delete_prompt,
    get_prompt_by_id,
    get_prompt_by_project,
    update_prompt,
)
from app.models import (
    PromptCreate,
    PromptPublic,
    PromptUpdate,
    UserProjectOrg,
    Pagination,
)
from app.utils import APIResponse


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prompt", tags=["Prompts"])


@router.post("/", response_model=APIResponse[PromptPublic], status_code=201)
def create_new_prompt(
    prompt_in: PromptCreate,
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Create a new prompt under the specified organization and project.
    """
    prompt = create_prompt(
        session=session, prompt_in=prompt_in, project_id=current_user.project_id
    )

    return APIResponse.success_response(prompt)


@router.patch("/{prompt_id}", response_model=APIResponse[PromptPublic])
def update_prompt_route(
    prompt_id: int = Path(..., gt=0),
    prompt_update: PromptUpdate = Depends(),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
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


@router.get("/{prompt_id}", response_model=APIResponse[PromptPublic])
def get_prompt_route(
    prompt_id: int = Path(..., gt=0),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Retrieve a single prompt by ID.
    """

    prompt = get_prompt_by_id(
        session=session, prompt_id=prompt_id, project_id=current_user.project_id
    )

    if not prompt:
        logger.error(
            f"[get_prompt] Prompt not found | prompt_id={prompt_id}, project_id={current_user.project_id}"
        )
        raise HTTPException(status_code=404, detail="Prompt not found.")

    return APIResponse.success_response(prompt)


@router.get("/", response_model=APIResponse[list[PromptPublic]])
def get_prompts_route(
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
    skip: int = Query(0, ge=0, description="How many items to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum items to return"),
):
    """
    Retrieve all prompts for the current project.
    """
    prompts = get_prompt_by_project(
        session=session, project_id=current_user.project_id, skip=skip, limit=limit
    )
    total = count_prompts_by_project(
        session=session, project_id=current_user.project_id
    )
    metadata = Pagination.build(
        total=total,
        skip=skip,
        limit=limit
    )
    return APIResponse.success_response(data=prompts, metadata=metadata)


@router.delete("/{prompt_id}", response_model=APIResponse)
def delete_prompt_route(
    prompt_id: int = Path(..., gt=0),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
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
