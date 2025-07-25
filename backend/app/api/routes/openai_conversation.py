from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlmodel import Session

from app.api.deps import get_db, get_current_user_org, get_current_user_org_project
from app.models import UserOrganization, UserProjectOrg
from app.models.openai_conversation import OpenAIConversationPublic
from app.crud.openai_conversation import (
    get_openai_conversation_by_id,
    get_openai_conversation_by_response_id,
    get_openai_conversations_by_ancestor,
    get_all_openai_conversations,
    delete_openai_conversation,
)
from app.utils import APIResponse

router = APIRouter(prefix="/openai-conversation", tags=["openai_conversation"])


@router.get(
    "/list",
    response_model=APIResponse[list[OpenAIConversationPublic]],
    summary="List all conversations",
    description="Retrieve all OpenAI conversations with pagination support",
)
async def list_conversations(
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, gt=0, le=100, description="Maximum number of records to return"
    ),
):
    """Get all conversations with pagination for project and organization"""
    conversations = get_all_openai_conversations(
        session=session, project_id=current_user.project_id, skip=skip, limit=limit
    )
    return APIResponse.success_response(
        data=[OpenAIConversationPublic.model_validate(conv) for conv in conversations]
    )


@router.get(
    "/{conversation_id}",
    response_model=APIResponse[OpenAIConversationPublic],
    summary="Get conversation by ID",
    description="Retrieve a conversation by its database ID",
)
async def get_conversation_by_id(
    conversation_id: int = Path(..., description="The conversation ID"),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """Get a conversation by its ID, only if it belongs to the user's project."""
    conversation = get_openai_conversation_by_id(
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
    summary="Get conversation by response ID",
    description="Retrieve a conversation by its response_id",
)
async def get_conversation_by_response_id(
    response_id: str = Path(..., description="The response ID"),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """Get a conversation by its response_id, only if it belongs to the user's project."""
    conversation = get_openai_conversation_by_response_id(
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
    response_model=APIResponse[list[OpenAIConversationPublic]],
    summary="Get conversations by ancestor",
    description="Retrieve all conversations that have the specified ancestor_response_id",
)
async def get_conversations_by_ancestor(
    ancestor_response_id: str = Path(..., description="The ancestor ID"),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """Get a conversation by its response_id, only if it belongs to the user's project."""
    conversation = get_openai_conversations_by_ancestor(
        session, ancestor_response_id, current_user.project_id
    )
    if not conversation:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation with ancestor ID {ancestor_response_id} not found.",
        )
    return APIResponse.success_response(conversation)


@router.delete(
    "/{conversation_id}",
    response_model=APIResponse[dict],
    summary="Delete conversation by ID",
    description="Delete a conversation by its database ID",
)
async def delete_conversation_by_id(
    conversation_id: int = Path(..., description="The conversation ID"),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """Delete a conversation by its ID, only if it belongs to the user's project."""
    conversation = get_openai_conversation_by_id(
        session, conversation_id, current_user.project_id
    )
    if not conversation or conversation.project_id != current_user.project_id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    success = delete_openai_conversation(session, conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return APIResponse.success_response(
        data={"message": "Conversation deleted successfully"}
    )
