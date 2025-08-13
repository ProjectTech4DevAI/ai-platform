import logging
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.deps import CurrentUserOrgProject, get_db
from app.crud import create_prompt_version, delete_prompt_version
from app.models import PromptVersionCreate, PromptVersionPublic
from app.utils import APIResponse


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prompts", tags=["Prompt Versions"])


@router.post(
    "/{prompt_id}/versions",
    response_model=APIResponse[PromptVersionPublic],
    status_code=201,
)
def create_prompt_version_route(
    prompt_version_in: PromptVersionCreate,
    prompt_id: UUID,
    current_user: CurrentUserOrgProject,
    session: Session = Depends(get_db),
):
    version = create_prompt_version(
        session=session,
        prompt_id=prompt_id,
        prompt_version_in=prompt_version_in,
        project_id=current_user.project_id,
    )
    return APIResponse.success_response(version)


@router.delete("/{prompt_id}/versions/{version_id}", response_model=APIResponse)
def delete_prompt_version_route(
    prompt_id: UUID,
    version_id: UUID,
    current_user: CurrentUserOrgProject,
    session: Session = Depends(get_db),
):
    """
    Delete a prompt version by ID.
    """
    delete_prompt_version(
        session=session,
        prompt_id=prompt_id,
        version_id=version_id,
        project_id=current_user.project_id
    )
    return APIResponse.success_response(
        data={"message": "Prompt version deleted successfully."}
    )