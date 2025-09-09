import logging

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
from app.models import CredsCreate, CredsPublic, CredsUpdate, UserProjectOrg
from app.utils import APIResponse
from app.core.providers import validate_provider
from app.core.exception_handlers import HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/credentials", tags=["credentials"])


@router.post(
    "/",
    response_model=APIResponse[list[CredsPublic]],
    summary="Create new credentials for the current organization and project",
    description="Creates new credentials for the caller's organization and project. Each organization can have different credentials for different providers and projects. Only one credential per provider is allowed per organization-project combination.",
)
def create_new_credential(
    *,
    session: SessionDep,
    creds_in: CredsCreate,
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
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
            logger.warning(
                f"[create_new_credential] Credentials for provider already exist | organization_id: {_current_user.organization_id}, project_id: {_current_user.project_id}, provider: {provider}"
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Credentials for provider '{provider}' already exist "
                    f"for this organization and project combination"
                ),
            )

    # Create credentials
    created_creds = set_creds_for_org(
        session=session,
        creds_add=creds_in,
        organization_id=_current_user.organization_id,
        project_id=_current_user.project_id,
    )
    if not created_creds:
        logger.error(
            f"[create_new_credential] Failed to create credentials | organization_id: {_current_user.organization_id}, project_id: {_current_user.project_id}"
        )
        raise HTTPException(status_code=500, detail="Failed to create credentials")

    return APIResponse.success_response([cred.to_public() for cred in created_creds])


@router.get(
    "/",
    response_model=APIResponse[list[CredsPublic]],
    summary="Get all credentials for current org and project",
    description="Retrieves all provider credentials associated with the caller's organization and project.",
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
        logger.error(
            f"[read_credential] No credentials found | organization_id: {_current_user.organization_id}, project_id: {_current_user.project_id}"
        )
        raise HTTPException(status_code=404, detail="Credentials not found")

    return APIResponse.success_response([cred.to_public() for cred in creds])


@router.get(
    "/provider/{provider}",
    response_model=APIResponse[dict],
    summary="Get specific provider credentials for current org and project",
    description="Retrieves credentials for a specific provider (e.g., 'openai', 'anthropic') for the caller's organization and project.",
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
    response_model=APIResponse[list[CredsPublic]],
    summary="Update credentials for current org and project",
    description="Updates credentials for a specific provider of the caller's organization and project.",
)
def update_credential(
    *,
    session: SessionDep,
    creds_in: CredsUpdate,
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    if not creds_in or not creds_in.provider or not creds_in.credential:
        logger.error(
            f"[update_credential] Invalid input | organization_id: {_current_user.organization_id}, project_id: {_current_user.project_id}"
        )
        raise HTTPException(
            status_code=400, detail="Provider and credential must be provided"
        )

    # Pass project_id directly to the CRUD function since CredsUpdate no longer has this field
    updated_credential = update_creds_for_org(
        session=session,
        org_id=_current_user.organization_id,
        creds_in=creds_in,
        project_id=_current_user.project_id,
    )

    return APIResponse.success_response(
        [cred.to_public() for cred in updated_credential]
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
    provider_creds = get_provider_credential(
        session=session,
        org_id=_current_user.organization_id,
        provider=provider_enum,
        project_id=_current_user.project_id,
    )
    if provider_creds is None:
        logger.error(
            f"[delete_provider_credential] Provider credentials not found | organization_id: {_current_user.organization_id}, provider: {provider}, project_id: {_current_user.project_id}"
        )
        raise HTTPException(status_code=404, detail="Provider credentials not found")

    remove_provider_credential(
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
    description="Removes all credentials for the caller's organization and project. This is a hard delete operation that permanently removes credentials from the database.",
)
def delete_all_credentials(
    *,
    session: SessionDep,
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    # First check if there are any credentials to delete
    existing_creds = get_creds_by_org(
        session=session,
        org_id=_current_user.organization_id,
        project_id=_current_user.project_id,
    )
    if not existing_creds:
        logger.error(
            f"[delete_all_credentials] Credentials not found | organization_id: {_current_user.organization_id}, project_id: {_current_user.project_id}"
        )
        raise HTTPException(
            status_code=404, detail="Credentials for organization/project not found"
        )

    # Delete all credentials
    remove_creds_for_org(
        session=session,
        org_id=_current_user.organization_id,
        project_id=_current_user.project_id,
    )

    return APIResponse.success_response(
        {"message": "All credentials deleted successfully"}
    )
