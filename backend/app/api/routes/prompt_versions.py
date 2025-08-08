import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlmodel import Session

from app.api.deps import get_db, get_current_user_org_project
from app.crud import (
    create_prompt_version,
    delete_prompt_version,
    get_prompt_version_by_id,
    get_prompt_versions_with_count,
    update_prompt_version,
)
from app.models import (
    PromptVersionCreate,
    PromptVersionPublic,
    PromptVersionUpdate,
    UserProjectOrg,
    Pagination,
)
from app.utils import APIResponse


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prompt", tags=["Prompt Versions"])


@router.post(
    "/{prompt_id}/version",
    response_model=APIResponse[PromptVersionPublic],
    status_code=201,
)
def create_prompt_version_route(
    prompt_version_in: PromptVersionCreate,
    prompt_id: int = Path(..., gt=0),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    version = create_prompt_version(
        session=session,
        prompt_id=prompt_id,
        prompt_version_in=prompt_version_in,
        project_id=current_user.project_id,
    )
    return APIResponse.success_response(version)


@router.get(
    "/{prompt_id}/version/{version}",
    response_model=APIResponse[PromptVersionPublic],
)
def get_prompt_version_by_id_route(
    prompt_id: int = Path(..., gt=0),
    version: int = Path(..., gt=0),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Fetch a specific prompt version.
    """
    prompt_version = get_prompt_version_by_id(
        session=session,
        prompt_id=prompt_id,
        version=version,
        project_id=current_user.project_id,
    )
    if not prompt_version:
        logger.error(
            f"[get_prompt_version_by_id_route] Prompt version not found | Prompt ID: {prompt_id}, Version ID: {version}, Project ID: {current_user.project_id}"
        )
        raise HTTPException(status_code=404, detail="Prompt version not found")

    return APIResponse.success_response(prompt_version)


@router.get(
    "/{prompt_id}/versions",
    response_model=APIResponse[list[PromptVersionPublic]],
)
def get_prompt_versions_route(
    prompt_id: int = Path(..., gt=0),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
    skip: int = Query(0, ge=0, description="How many items to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum items to return"),
):
    """
    Fetch all prompt versions for a given prompt ID.
    """
    prompt_versions, total = get_prompt_versions_with_count(
        session=session,
        prompt_id=prompt_id,
        project_id=current_user.project_id,
        skip=skip,
        limit=limit,
    )

    metadata = Pagination.build(
        total=total,
        skip=skip,
        limit=limit,
    )
    return APIResponse.success_response(data=prompt_versions, metadata=metadata)


@router.patch(
    "/{prompt_id}/version/{version}",
    response_model=APIResponse[PromptVersionPublic],
)
def update_prompt_version_route(
    prompt_version_update: PromptVersionUpdate,
    prompt_id: int = Path(..., gt=0),
    version: int = Path(..., gt=0),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Update a specific prompt version to production or staging.
    """
    updated_version = update_prompt_version(
        session=session,
        prompt_id=prompt_id,
        prompt_version_in=prompt_version_update,
        project_id=current_user.project_id,
        version=version,
    )
    return APIResponse.success_response(updated_version)


@router.delete(
    "/{prompt_id}/version/{version}",
    response_model=APIResponse,
)
def delete_prompt_version_route(
    prompt_id: int = Path(..., gt=0),
    version: int = Path(..., gt=0),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Delete a specific prompt version by its ID.
    """
    delete_prompt_version(
        session=session,
        prompt_id=prompt_id,
        version=version,
        project_id=current_user.project_id,
    )
    return APIResponse.success_response(
        data={"message": "Prompt version deleted successfully"}
    )
