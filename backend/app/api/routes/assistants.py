from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlmodel import Session

from app.api.deps import get_db, get_current_user_org_project
from app.crud import (
    fetch_assistant_from_openai,
    sync_assistant,
    create_assistant
)
from app.models import UserProjectOrg, AssistantCreate
from app.utils import APIResponse, get_openai_client

router = APIRouter(prefix="/assistant", tags=["Assistants"])


@router.post(
    "/{assistant_id}/ingest",
    response_model=APIResponse,
    status_code=201,
)
def ingest_assistant_route(
    assistant_id: Annotated[str, Path(description="The ID of the assistant to ingest")],
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Ingest an assistant from OpenAI and store it in the platform.
    """

    client = get_openai_client(
        session, current_user.organization_id, current_user.project_id
    )

    openai_assistant = fetch_assistant_from_openai(assistant_id, client)
    assistant = sync_assistant(
        session=session,
        organization_id=current_user.organization_id,
        project_id=current_user.project_id,
        openai_assistant=openai_assistant,
    )

    return APIResponse.success_response(assistant)


@router.post("/", response_model=APIResponse, status_code=201)
def create_assistant_route(
    assistant_in: AssistantCreate,
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Create a new assistant in the local DB, checking that vector store IDs exist in OpenAI first.
    """
    client = get_openai_client(
        session, current_user.organization_id, current_user.project_id
    )
    assistant = create_assistant(
        session=session,
        openai_client=client,
        assistant=assistant_in,
        project_id=current_user.project_id,
        organization_id=current_user.organization_id,
    )
    return APIResponse.success_response(assistant)