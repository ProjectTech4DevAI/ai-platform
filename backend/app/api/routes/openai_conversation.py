from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlmodel import Session

from app.api.deps import get_db, get_current_user_org, get_current_user_org_project
from app.models import UserOrganization, UserProjectOrg
from app.models.openai_conversation import (
    OpenAIConversationCreate,
    OpenAIConversationUpdate,
    OpenAIConversationPublic,
)
from app.crud.openai_conversation import (
    create_openai_conversation,
    get_openai_conversation_by_id,
    get_openai_conversation_by_response_id,
    get_openai_conversations_by_ancestor,
    get_all_openai_conversations,
    update_openai_conversation,
    delete_openai_conversation,
)
from app.utils import APIResponse

router = APIRouter(prefix="/openai-conversation", tags=["openai_conversation"])


@router.post(
    "/create",
    response_model=APIResponse[OpenAIConversationPublic],
    summary="Create a new OpenAI conversation",
    description="Create a new conversation entry with response_id, ancestor_response_id, and previous_response_id",
)
async def create_conversation(
    conversation_data: OpenAIConversationCreate,
    db: Session = Depends(get_db),
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """Create a new OpenAI conversation entry."""
    try:
        conversation = create_openai_conversation(db, conversation_data)
        return APIResponse.success_response(
            data=OpenAIConversationPublic.model_validate(conversation)
        )
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to create conversation: {str(e)}"
        )


@router.get(
    "/list",
    response_model=APIResponse[list[OpenAIConversationPublic]],
    summary="List all conversations",
    description="Retrieve all conversations with pagination support",
)
async def list_conversations(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, gt=0, le=1000, description="Maximum number of records to return"
    ),
    db: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
):
    """Get all conversations with pagination."""
    conversations = get_all_openai_conversations(db, skip=skip, limit=limit)
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
    db: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
):
    """Get a conversation by its ID."""
    conversation = get_openai_conversation_by_id(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return APIResponse.success_response(
        data=OpenAIConversationPublic.model_validate(conversation)
    )


@router.get(
    "/response/{response_id}",
    response_model=APIResponse[OpenAIConversationPublic],
    summary="Get conversation by response ID",
    description="Retrieve a conversation by its response_id",
)
async def get_conversation_by_response_id(
    response_id: str = Path(..., description="The response ID"),
    db: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
):
    """Get a conversation by its response_id."""
    conversation = get_openai_conversation_by_response_id(db, response_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return APIResponse.success_response(
        data=OpenAIConversationPublic.model_validate(conversation)
    )


@router.get(
    "/ancestor/{ancestor_response_id}",
    response_model=APIResponse[list[OpenAIConversationPublic]],
    summary="Get conversations by ancestor",
    description="Retrieve all conversations that have the specified ancestor_response_id",
)
async def get_conversations_by_ancestor(
    ancestor_response_id: str = Path(..., description="The ancestor response ID"),
    db: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
):
    """Get all conversations by ancestor_response_id."""
    conversations = get_openai_conversations_by_ancestor(db, ancestor_response_id)
    return APIResponse.success_response(
        data=[OpenAIConversationPublic.model_validate(conv) for conv in conversations]
    )


@router.put(
    "/{conversation_id}",
    response_model=APIResponse[OpenAIConversationPublic],
    summary="Update conversation",
    description="Update an existing conversation by ID",
)
async def update_conversation(
    conversation_data: OpenAIConversationUpdate,
    conversation_id: int = Path(..., description="The conversation ID"),
    db: Session = Depends(get_db),
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """Update a conversation by its ID."""
    conversation = update_openai_conversation(db, conversation_id, conversation_data)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return APIResponse.success_response(
        data=OpenAIConversationPublic.model_validate(conversation)
    )


@router.delete(
    "/{conversation_id}",
    response_model=APIResponse[dict],
    summary="Delete conversation by ID",
    description="Delete a conversation by its database ID",
)
async def delete_conversation_by_id(
    conversation_id: int = Path(..., description="The conversation ID"),
    db: Session = Depends(get_db),
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """Delete a conversation by its ID."""
    success = delete_openai_conversation(db, conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return APIResponse.success_response(
        data={"message": "Conversation deleted successfully"}
    )
