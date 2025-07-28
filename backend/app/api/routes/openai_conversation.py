from typing import Annotated

from fastapi import APIRouter, Depends, Path, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_db, get_current_user_org_project
from app.crud import (
    get_conversation_by_id,
    get_conversation_by_response_id,
    get_conversation_by_ancestor_id,
    get_conversations_by_project,
    get_conversations_count_by_project,
    create_conversation,
    delete_conversation,
)
from app.models import (
    UserProjectOrg,
    OpenAIConversationCreate,
    OpenAIConversation,
    OpenAIConversationPublic,
)
from app.utils import APIResponse

router = APIRouter(prefix="/openai-conversation", tags=["OpenAI Conversations"])


@router.get(
    "/{conversation_id}",
    response_model=APIResponse[OpenAIConversationPublic],
    summary="Get a single conversation by its ID",
)
def get_conversation_route(
    conversation_id: int = Path(..., description="The conversation ID to fetch"),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Fetch a single conversation by its ID.
    """
    conversation = get_conversation_by_id(
        session, conversation_id, current_user.project_id
    )
    if not conversation:
        raise HTTPException(
            status_code=404, detail=f"Conversation with ID {conversation_id} not found."
        )
    return APIResponse.success_response(conversation)


@router.get(
    "/response/{response_id}",
    response_model=APIResponse[OpenAIConversationPublic],
    summary="Get a conversation by its OpenAI response ID",
)
def get_conversation_by_response_id_route(
    response_id: str = Path(..., description="The OpenAI response ID to fetch"),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Fetch a conversation by its OpenAI response ID.
    """
    conversation = get_conversation_by_response_id(
        session, response_id, current_user.project_id
    )
    if not conversation:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation with response ID {response_id} not found.",
        )
    return APIResponse.success_response(conversation)


@router.get(
    "/ancestor/{ancestor_response_id}",
    response_model=APIResponse[OpenAIConversationPublic],
    summary="Get a conversation by its ancestor response ID",
)
def get_conversation_by_ancestor_id_route(
    ancestor_response_id: str = Path(
        ..., description="The ancestor response ID to fetch"
    ),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Fetch a conversation by its ancestor response ID.
    """
    conversation = get_conversation_by_ancestor_id(
        session, ancestor_response_id, current_user.project_id
    )
    if not conversation:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation with ancestor response ID {ancestor_response_id} not found.",
        )
    return APIResponse.success_response(conversation)


@router.get(
    "/",
    response_model=APIResponse[list[OpenAIConversationPublic]],
    summary="List all conversations in the current project",
)
def list_conversations_route(
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
    skip: int = Query(0, ge=0, description="How many items to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum items to return"),
):
    """
    List all conversations in the current project.
    """
    conversations = get_conversations_by_project(
        session=session,
        project_id=current_user.project_id,
        skip=skip,  # ← Pagination offset
        limit=limit,  # ← Page size
    )

    # Get total count for pagination metadata
    total = get_conversations_count_by_project(
        session=session,
        project_id=current_user.project_id,
    )

    return APIResponse.success_response(
        data=conversations, metadata={"skip": skip, "limit": limit, "total": total}
    )


@router.delete("/{conversation_id}", response_model=APIResponse)
def delete_conversation_route(
    conversation_id: Annotated[int, Path(description="Conversation ID to delete")],
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Soft delete a conversation by marking it as deleted.
    """
    deleted_conversation = delete_conversation(
        session=session,
        conversation_id=conversation_id,
        project_id=current_user.project_id,
    )

    if not deleted_conversation:
        raise HTTPException(
            status_code=404, detail=f"Conversation with ID {conversation_id} not found."
        )

    return APIResponse.success_response(
        data={"message": "Conversation deleted successfully."}
    )
