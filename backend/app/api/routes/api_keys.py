import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_active_superuser, get_db
from app.crud.api_key import (
    create_api_key,
    delete_api_key,
    get_api_key,
    get_api_key_by_user_org,
    get_api_keys_by_organization,
)
from app.crud.organization import validate_organization
from app.models import APIKeyPublic, User
from app.utils import APIResponse

router = APIRouter(prefix="/apikeys", tags=["API Keys"])


# Create API Key
@router.post("/", response_model=APIResponse[APIKeyPublic])
def create_key(
    organization_id: int,
    user_id: uuid.UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """
    Generate a new API key for the user's organization.
    """
    try:
        # Validate organization
        validate_organization(session, organization_id)

        existing_api_key = get_api_key_by_user_org(session, organization_id, user_id)
        if existing_api_key:
            raise HTTPException(
                status_code=400,
                detail="API Key already exists for this user and organization",
            )

        # Create and return API key
        api_key = create_api_key(
            session, organization_id=organization_id, user_id=user_id
        )
        return APIResponse.success_response(api_key)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# List API Keys
@router.get("/", response_model=APIResponse[list[APIKeyPublic]])
def list_keys(
    organization_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """
    Retrieve all API keys for the user's organization.
    """
    try:
        # Validate organization
        validate_organization(session, organization_id)

        # Retrieve API keys
        api_keys = get_api_keys_by_organization(session, organization_id)
        return APIResponse.success_response(api_keys)

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
