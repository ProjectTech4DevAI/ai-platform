import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.api.deps import get_db, get_current_active_superuser
from app.crud.api_key import (
    create_api_key,
    get_api_key,
    delete_api_key,
    get_api_key_by_project,
)
from app.crud.project import validate_project
from app.models import APIKeyPublic, User
from app.utils import APIResponse

router = APIRouter(prefix="/apikeys", tags=["API Keys"])


# Create API Key
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
    try:
        # Validate organization
        project = validate_project(session, project_id)

        existing_api_key = get_api_key_by_project(session, project_id)
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

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# List API Keys
@router.get("/", response_model=APIResponse[APIKeyPublic])
def list_keys(
    project_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """
    Retrieve all API keys for the given project.
    """
    try:
        # Validate project
        project = validate_project(session=session, project_id=project_id)

        # Retrieve the API key for this project (regardless of user)
        api_key = get_api_key_by_project(session=session, project_id=project_id)
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found for project")

        return APIResponse.success_response(api_key)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Get API Key by ID
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
        raise HTTPException(status_code=404, detail="API Key does not exist")

    return APIResponse.success_response(api_key)


# Revoke API Key (Soft Delete)
@router.delete("/{api_key_id}", response_model=APIResponse[dict])
def revoke_key(
    api_key_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """
    Soft delete an API key (revoke access).
    """
    try:
        delete_api_key(session, api_key_id)
        return APIResponse.success_response({"message": "API key revoked successfully"})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
