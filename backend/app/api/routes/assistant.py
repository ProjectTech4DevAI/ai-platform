from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlmodel import Session

from app.api.deps import get_db, get_current_user_org_project
from app.core.util import configure_openai
from app.crud import (
    fetch_assistant_from_openai,
    get_provider_credential,
    insert_assistant,
)
from app.models import UserProjectOrg
from app.utils import APIResponse

router = APIRouter(prefix="/assistant", tags=["Assistants"])


@router.post(
    "/{assistant_id}/ingest",
    response_model=APIResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_assistant_route(
    assistant_id: Annotated[str, Path(description="The ID of the assistant to ingest")],
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Ingest an assistant from OpenAI and store it in the platform.
    """
    credentials = get_provider_credential(
        session=session,
        org_id=current_user.organization_id,
        provider="openai",
        project_id=current_user.project_id,
    )
    client, success = configure_openai(credentials)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenAI not configured for this organization.",
        )

    openai_assistant = fetch_assistant_from_openai(assistant_id, client)
    assistant = insert_assistant(
        session=session,
        organization_id=current_user.organization_id,
        project_id=current_user.project_id,
        openai_assistant=openai_assistant,
    )

    return APIResponse.success_response(assistant)
