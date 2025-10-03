from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.api.deps import get_db, get_current_active_superuser, get_user_context
from app.crud.api_key import APIKeyCrud
from app.models import APIKeyPublic, APIKeyCreateResponse, User, UserContext
from app.utils import APIResponse

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.post("/", response_model=APIResponse[APIKeyCreateResponse], status_code=201)
def create_api_key_route(
    project_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """
    Create a new API key for the current project.

    The raw API key is returned only once during creation.
    Store it securely as it cannot be retrieved again.
    """
    api_key_crud = APIKeyCrud(session=session, project_id=project_id)
    raw_key, api_key = api_key_crud.create(
        user_id=current_user.id,
    )

    api_key = APIKeyCreateResponse(**api_key.model_dump(), key=raw_key)

    return APIResponse.success_response(api_key)


@router.get("/", response_model=APIResponse[list[APIKeyPublic]])
def list_api_keys_route(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum records to return"),
):
    """
    List all API keys for the current project.

    Returns masked keys for security - the full key is only shown during creation.
    Supports pagination via skip and limit parameters.
    """
    crud = APIKeyCrud(session, current_user.project_id)
    api_keys = crud.read_all(skip=skip, limit=limit)

    return APIResponse.success_response(api_keys)
