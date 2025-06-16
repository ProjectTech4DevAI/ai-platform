import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.api.deps import get_db, get_current_active_superuser
from app.crud.api_key import (
    create_api_key,
    get_api_key,
    delete_api_key,
    get_api_keys_by_project,
    get_api_key_by_project_user,
)
from app.crud.project import validate_project
from app.models import APIKeyPublic, User
from app.utils import APIResponse
from app.core.exception_handlers import HTTPException

router = APIRouter(prefix="/apikeys", tags=["API Keys"])


@router.post("/", response_model=APIResponse[APIKeyPublic])
def create_key(
    project_id: int,
    user_id: uuid.UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """
    Generate a new API key for the user's organization.
    """
    # Validate organization
    project = validate_project(session, project_id)

    existing_api_key = get_api_key_by_project_user(session, project_id, user_id)
    if existing_api_key:
        raise HTTPException(
            status_code=400,
            detail="API Key already exists for this user and project.",
        )

    # Create and return API key
    api_key = create_api_key(
        session,
        organization_id=project.organization_id,
        user_id=user_id,
        project_id=project_id,
    )
    return APIResponse.success_response(api_key)


@router.get("/", response_model=APIResponse[list[APIKeyPublic]])
def list_keys(
    project_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """
    Retrieve all API keys for the given project. Superusers get all keys;
    regular users get only their own.
    """
    # Validate project
    project = validate_project(session=session, project_id=project_id)

    if current_user.is_superuser:
        # Superuser: fetch all API keys for the project
        api_keys = get_api_keys_by_project(session=session, project_id=project_id)
    else:
        # Regular user: fetch only their own API key
        user_api_key = get_api_key_by_project_user(
            session=session, project_id=project_id, user_id=current_user.id
        )
        api_keys = [user_api_key] if user_api_key else []

    # Raise an exception if no API keys are found for the project
    if not api_keys:
        raise HTTPException(
            status_code=404,
            detail="No API keys found for this project.",
        )

    return APIResponse.success_response(api_keys)


@router.get("/{api_key_id}", response_model=APIResponse[APIKeyPublic])
def get_key(
    api_key_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """
    Retrieve an API key by ID.
    """
    api_key = get_api_key(session, api_key_id)
    if not api_key:
        raise HTTPException(404, "API Key does not exist")

    return APIResponse.success_response(api_key)


@router.delete("/{api_key_id}", response_model=APIResponse[dict])
def revoke_key(
    api_key_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """
    Soft delete an API key (revoke access).
    """
    api_key = get_api_key(session, api_key_id)

    if not api_key:
        raise HTTPException(404, "API key not found or already deleted")

    delete_api_key(session, api_key_id)

    return APIResponse.success_response({"message": "API key revoked successfully"})
