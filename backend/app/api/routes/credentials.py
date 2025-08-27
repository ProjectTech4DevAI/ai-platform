from typing import List

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep, get_current_user_org_project
from app.crud.credentials import (
    get_creds_by_org,
    get_provider_credential,
    remove_creds_for_org,
    set_creds_for_org,
    update_creds_for_org,
    remove_provider_credential,
)
from app.crud import validate_organization
from app.models import CredsCreate, CredsPublic, CredsUpdate, UserProjectOrg
from app.utils import APIResponse
from app.core.providers import validate_provider
from app.core.exception_handlers import HTTPException

router = APIRouter(prefix="/credentials", tags=["credentials"])


@router.post(
    "/",
    response_model=APIResponse[List[CredsPublic]],
    summary="Create new credentials for the current organization and project",
    description="Creates new credentials for the caller's organization and project as derived from the API key. Each organization can have different credentials for different providers and projects. Only one credential per provider is allowed per organization-project combination.",
)
def create_new_credential(
    *,
    session: SessionDep,
    creds_in: CredsCreate,
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    # Validate organization
    validate_organization(session, _current_user.organization_id)

    # Project comes from API key context; no cross-org check needed here

    # Prevent duplicate credentials
    for provider in creds_in.credential.keys():
        existing_cred = get_provider_credential(
            session=session,
            org_id=_current_user.organization_id,
            provider=provider,
            project_id=_current_user.project_id,
        )
        if existing_cred:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Credentials for provider '{provider}' already exist "
                    f"for this organization and project combination"
                ),
            )

    # Create credentials
    credential = set_creds_for_org(
        session=session,
        creds_add=creds_in,
        organization_id=_current_user.organization_id,
        project_id=_current_user.project_id,
    )
    if not credential:
        raise Exception(status_code=500, detail="Failed to create credentials")

    return APIResponse.success_response([cred.to_public() for cred in new_creds])


@router.get(
    "/",
    response_model=APIResponse[List[CredsPublic]],
    summary="Get all credentials for current org and project",
    description="Retrieves all provider credentials associated with the caller's organization and project derived from the API key.",
)
def read_credential(
    *,
    session: SessionDep,
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    creds = get_creds_by_org(
        session=session,
        org_id=_current_user.organization_id,
        project_id=_current_user.project_id,
    )
    if not creds:
        raise HTTPException(status_code=404, detail="Credentials not found")

    return APIResponse.success_response([cred.to_public() for cred in creds])


@router.get(
    "/provider/{provider}",
    response_model=APIResponse[dict],
    summary="Get specific provider credentials for current org and project",
    description="Retrieves credentials for a specific provider (e.g., 'openai', 'anthropic') for the caller's organization and project derived from the API key.",
)
def read_provider_credential(
    *,
    session: SessionDep,
    provider: str,
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    provider_enum = validate_provider(provider)
    credential = get_provider_credential(
        session=session,
        org_id=_current_user.organization_id,
        provider=provider_enum,
        project_id=_current_user.project_id,
    )
    if credential is None:
        raise HTTPException(status_code=404, detail="Provider credentials not found")

    return APIResponse.success_response(credential)


@router.patch(
    "/",
    response_model=APIResponse[List[CredsPublic]],
    summary="Update credentials for current org and project",
    description="Updates credentials for a specific provider of the caller's organization and project derived from the API key.",
)
def update_credential(
    *,
    session: SessionDep,
    creds_in: CredsUpdate,
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    validate_organization(session, _current_user.organization_id)
    if not creds_in or not creds_in.provider or not creds_in.credential:
        raise HTTPException(
            status_code=400, detail="Provider and credential must be provided"
        )

    # Pass project_id directly to the CRUD function since CredsUpdate no longer has this field
    update_credential = update_creds_for_org(
        session=session,
        org_id=_current_user.organization_id,
        creds_in=creds_in,
        project_id=_current_user.project_id,
    )

    return APIResponse.success_response(
        [cred.to_public() for cred in update_credential]
    )


@router.delete(
    "/provider/{provider}",
    response_model=APIResponse[dict],
    summary="Delete specific provider credentials for current org and project",
)
def delete_provider_credential(
    *,
    session: SessionDep,
    provider: str,
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    provider_enum = validate_provider(provider)
    if not provider_enum:
        raise HTTPException(status_code=400, detail="Invalid provider")
    provider_creds = get_provider_credential(
        session=session,
        org_id=_current_user.organization_id,
        provider=provider_enum,
        project_id=_current_user.project_id,
    )
    if provider_creds is None:
        raise HTTPException(status_code=404, detail="Provider credentials not found")

    updated_creds = remove_provider_credential(
        session=session,
        org_id=_current_user.organization_id,
        provider=provider_enum,
        project_id=_current_user.project_id,
    )

    return APIResponse.success_response(
        {"message": "Provider credentials removed successfully"}
    )


@router.delete(
    "/",
    response_model=APIResponse[dict],
    summary="Delete all credentials for current org and project",
    description="Removes all credentials for the caller's organization and project derived from the API key. This is a soft delete operation that marks credentials as inactive.",
)
def delete_all_credentials(
    *,
    session: SessionDep,
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    creds = remove_creds_for_org(
        session=session,
        org_id=_current_user.organization_id,
        project_id=_current_user.project_id,
    )
    if not creds:
        raise HTTPException(
            status_code=404, detail="Credentials for organization not found"
        )

    return APIResponse.success_response({"message": "Credentials deleted successfully"})
