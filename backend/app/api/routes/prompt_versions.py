import logging

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user_org_project, UserProjectOrg
from app.crud import (
    create_prompt_version,
    delete_prompt_version,
    get_prompt_version_by_id,
    get_prompt_versions,
    update_prompt_version,
)
from app.models import (
    PromptVersionCreate,
    PromptVersionPublic,
    PromptVersionUpdate,
)
from app.utils import APIResponse


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prompt", tags=["Prompt Versions"])


@router.post(
    "/{prompt_id}/version",
    response_model=APIResponse[PromptVersionPublic],
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
        current_user=current_user,
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
):
    """
    Fetch all prompt versions for a given prompt ID.
    """
    prompt_versions = get_prompt_versions(
        session=session,
        prompt_id=prompt_id,
        project_id=current_user.project_id,
    )

    return APIResponse.success_response(prompt_versions)


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
        current_user=current_user,
    )
    return APIResponse.success_response(
        data={"message": "Prompt version deleted successfully"}
    )
