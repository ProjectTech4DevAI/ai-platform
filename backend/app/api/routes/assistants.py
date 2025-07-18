from typing import Annotated

from fastapi import APIRouter, Depends, Path, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_db, get_current_user_org_project
from app.crud import (
    fetch_assistant_from_openai,
    sync_assistant,
    create_assistant,
    update_assistant,
    get_assistant_by_id,
    get_assistants_by_project
)
from app.models import UserProjectOrg, AssistantCreate, AssistantUpdate, Assistant
from app.utils import APIResponse, get_openai_client

router = APIRouter(prefix="/assistant", tags=["Assistants"])


@router.post(
    "/{assistant_id}/ingest",
    response_model=APIResponse[Assistant],
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


@router.post("/", response_model=APIResponse[Assistant], status_code=201)
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


@router.put("/{assistant_id}", response_model=APIResponse[Assistant])
def update_assistant_route(
    assistant_id: Annotated[str, Path(description="Assistant ID to update")],
    assistant_update: AssistantUpdate,
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Update an existing assistant with provided fields. Supports replacing, adding, or removing vector store IDs.
    """
    client = get_openai_client(
        session, current_user.organization_id, current_user.project_id
    )
    updated_assistant = update_assistant(
        session=session,
        assistant_id=assistant_id,
        openai_client=client,
        project_id=current_user.project_id,
        organization_id=current_user.organization_id,
        assistant_update=assistant_update,
    )
    return APIResponse.success_response(updated_assistant)


@router.get(
    "/{assistant_id}",
    response_model=APIResponse[Assistant],
    summary="Get a single assistant by its ID",
)
def get_assistant_route(
    assistant_id: str = Path(..., description="The assistant_id to fetch"),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project)
):
    """
    Fetch a single assistant by its assistant_id.
    """
    assistant = get_assistant_by_id(
        session,
        assistant_id,
        current_user.project_id
    )
    if not assistant:
        raise HTTPException(
            status_code=404,
            detail=f"Assistant with ID {assistant_id} not found."
        )
    return APIResponse.success_response(assistant)


@router.get(
    "/{assistant_id}",
    response_model=APIResponse[Assistant],
    summary="Get a single assistant by its ID",
)
def get_assistant_route(
    assistant_id: str = Path(..., description="The assistant_id to fetch"),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project)
):
    """
    Fetch a single assistant by its assistant_id.
    """
    assistant = get_assistant_by_id(
        session,
        assistant_id,
        current_user.project_id
    )
    if not assistant:
        raise HTTPException(
            status_code=404,
            detail=f"Assistant with ID {assistant_id} not found."
        )
    return APIResponse.success_response(assistant)
    

@router.get(
    "/",
    response_model=APIResponse,
    summary="List all assistants in the current project"
)
def list_assistants_route(
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
    skip: int = Query(0, ge=0, description="How many items to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum items to return"),
):
    """
    List all assistants in the current project and organization.
    """

    assistants = get_assistants_by_project(
        session=session,
        project_id=current_user.project_id,
        skip=skip,
        limit=limit
    )
    return APIResponse.success_response(assistants)