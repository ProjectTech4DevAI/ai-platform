from typing import Annotated

from fastapi import APIRouter, Depends, Path, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_db, get_current_user_org_project
from app.crud import (
    get_conversation_by_id,
    get_conversation_by_response_id,
    get_conversations_by_project,
    get_conversations_by_assistant,
    get_conversation_thread,
    create_conversation,
    update_conversation,
    delete_conversation,
    upsert_conversation,
)
from app.models import (
    UserProjectOrg,
    OpenAIConversationCreate,
    OpenAIConversationUpdate,
    OpenAIConversation,
)
from app.utils import APIResponse

router = APIRouter(prefix="/openai-conversation", tags=["OpenAI Conversations"])


@router.post("/", response_model=APIResponse[OpenAIConversation], status_code=201)
def create_conversation_route(
    conversation_in: OpenAIConversationCreate,
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Create a new OpenAI conversation in the database.
    """
    conversation = create_conversation(
        session=session,
        conversation=conversation_in,
        project_id=current_user.project_id,
        organization_id=current_user.organization_id,
    )
    return APIResponse.success_response(conversation)


@router.post("/upsert", response_model=APIResponse[OpenAIConversation], status_code=201)
def upsert_conversation_route(
    conversation_in: OpenAIConversationCreate,
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Create a new conversation or update existing one if response_id already exists.
    """
    conversation = upsert_conversation(
        session=session,
        conversation=conversation_in,
        project_id=current_user.project_id,
        organization_id=current_user.organization_id,
    )
    return APIResponse.success_response(conversation)


@router.patch("/{conversation_id}", response_model=APIResponse[OpenAIConversation])
def update_conversation_route(
    conversation_id: Annotated[int, Path(description="Conversation ID to update")],
    conversation_update: OpenAIConversationUpdate,
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Update an existing conversation with provided fields.
    """
    updated_conversation = update_conversation(
        session=session,
        conversation_id=conversation_id,
        project_id=current_user.project_id,
        conversation_update=conversation_update,
    )

    if not updated_conversation:
        raise HTTPException(
            status_code=404, detail=f"Conversation with ID {conversation_id} not found."
        )

    return APIResponse.success_response(updated_conversation)


@router.get(
    "/{conversation_id}",
    response_model=APIResponse[OpenAIConversation],
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
    response_model=APIResponse[OpenAIConversation],
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
    "/thread/{response_id}",
    response_model=APIResponse[list[OpenAIConversation]],
    summary="Get the full conversation thread starting from a response ID",
)
def get_conversation_thread_route(
    response_id: str = Path(
        ..., description="The response ID to start the thread from"
    ),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Get the full conversation thread starting from a given response ID.
    This includes all ancestor and previous responses in the conversation chain.
    """
    thread_conversations = get_conversation_thread(
        session=session,
        response_id=response_id,
        project_id=current_user.project_id,
    )
    return APIResponse.success_response(thread_conversations)


@router.get(
    "/",
    response_model=APIResponse[list[OpenAIConversation]],
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
        session=session, project_id=current_user.project_id, skip=skip, limit=limit
    )
    return APIResponse.success_response(conversations)


@router.get(
    "/assistant/{assistant_id}",
    response_model=APIResponse[list[OpenAIConversation]],
    summary="List all conversations for a specific assistant",
)
def list_conversations_by_assistant_route(
    assistant_id: str = Path(..., description="The assistant ID to filter by"),
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
    skip: int = Query(0, ge=0, description="How many items to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum items to return"),
):
    """
    List all conversations for a specific assistant in the current project.
    """
    conversations = get_conversations_by_assistant(
        session=session,
        assistant_id=assistant_id,
        project_id=current_user.project_id,
        skip=skip,
        limit=limit,
    )
    return APIResponse.success_response(conversations)


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
