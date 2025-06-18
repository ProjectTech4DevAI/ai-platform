import logging
from typing import List

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep, get_current_active_superuser
from app.crud.credentials import (
    get_creds_by_org,
    get_provider_credential,
    remove_creds_for_org,
    set_creds_for_org,
    update_creds_for_org,
    remove_provider_credential,
)
from app.crud import validate_organization, validate_project
from app.models import CredsCreate, CredsPublic, CredsUpdate
from app.models.organization import Organization
from app.models.project import Project
from app.utils import APIResponse
from app.core.providers import validate_provider
from app.core.exception_handlers import HTTPException

router = APIRouter(prefix="/credentials", tags=["credentials"])
logger = logging.getLogger("app.routes.credentials")


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[List[CredsPublic]],
    summary="Create new credentials for an organization and project",
    description="Creates new credentials for a specific organization and project combination. This endpoint requires superuser privileges. Each organization can have different credentials for different providers and projects. Only one credential per provider is allowed per organization-project combination.",
)
def create_new_credential(*, session: SessionDep, creds_in: CredsCreate):
    logger.info(f"[credential.create] Creating credentials | org_id={creds_in.organization_id}, project_id={creds_in.project_id}")
    
    # Validate organization
    validate_organization(session, creds_in.organization_id)

    # Validate project if provided
    if creds_in.project_id:
        project = validate_project(session, creds_in.project_id)
        if project.organization_id != creds_in.organization_id:
            logger.warning(f"[credential.create] Project does not belong to organization | org_id={creds_in.organization_id}, project_id={creds_in.project_id}")
            raise HTTPException(
                status_code=400,
                detail="Project does not belong to the specified organization",
            )

    # Prevent duplicate credentials
    for provider in creds_in.credential.keys():
        existing_cred = get_provider_credential(
            session=session,
            org_id=creds_in.organization_id,
            provider=provider,
            project_id=creds_in.project_id,
        )
        if existing_cred:
            logger.warning(f"[credential.create] Credential exists | provider={provider}, org_id={creds_in.organization_id}, project_id={creds_in.project_id}")
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Credentials for provider '{provider}' already exist "
                    f"for this organization and project combination"
                ),
            )

    # Create credentials
    new_creds = set_creds_for_org(session=session, creds_add=creds_in)
    if not new_creds:
        logger.error(f"[credential.create] Failed to create credentials | org_id={creds_in.organization_id}")
        raise Exception(status_code=500, detail="Failed to create credentials")

    logger.info(f"[credential.create] Credentials created | count={len(new_creds)}, org_id={creds_in.organization_id}")
    return APIResponse.success_response([cred.to_public() for cred in new_creds])


@router.get(
    "/{org_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[List[CredsPublic]],
    summary="Get all credentials for an organization and project",
    description="Retrieves all provider credentials associated with a specific organization and project combination. If project_id is not provided, returns credentials for the organization level. This endpoint requires superuser privileges.",
)
def read_credential(*, session: SessionDep, org_id: int, project_id: int | None = None):
    logger.info(f"[credential.read] Fetching credentials | org_id={org_id}, project_id={project_id}")
    creds = get_creds_by_org(session=session, org_id=org_id, project_id=project_id)
    if not creds:
        logger.warning(f"[credential.read] No credentials found | org_id={org_id}, project_id={project_id}")
        raise HTTPException(status_code=404, detail="Credentials not found")

    logger.info(f"[credential.read] Retrieved {len(creds)} credentials | org_id={org_id}, project_id={project_id}")
    return APIResponse.success_response([cred.to_public() for cred in creds])


@router.get(
    "/{org_id}/{provider}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[dict],
    summary="Get specific provider credentials for an organization and project",
    description="Retrieves credentials for a specific provider (e.g., 'openai', 'anthropic') for a given organization and project combination. If project_id is not provided, returns organization-level credentials. This endpoint requires superuser privileges.",
)
def read_provider_credential(
    *, session: SessionDep, org_id: int, provider: str, project_id: int | None = None
):
    logger.info(f"[credential.read_provider] Fetching provider credential | org_id={org_id}, provider={provider}, project_id={project_id}")
    provider_enum = validate_provider(provider)
    provider_creds = get_provider_credential(
        session=session,
        org_id=org_id,
        provider=provider_enum,
        project_id=project_id,
    )
    if provider_creds is None:
        logger.warning(f"[credential.read_provider] Credential not found | org_id={org_id}, provider={provider}, project_id={project_id}")
        raise HTTPException(status_code=404, detail="Provider credentials not found")

    logger.info(f"[credential.read_provider] Credential found | org_id={org_id}, provider={provider}, project_id={project_id}")
    return APIResponse.success_response(provider_creds)


@router.patch(
    "/{org_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[List[CredsPublic]],
    summary="Update organization and project credentials",
    description="Updates credentials for a specific organization and project combination. Can update specific provider credentials or add new providers. If project_id is provided in the update, credentials will be moved to that project. This endpoint requires superuser privileges.",
)
def update_credential(*, session: SessionDep, org_id: int, creds_in: CredsUpdate):
    logger.info(f"[credential.update] Updating credentials | org_id={org_id}, provider={creds_in.provider}, project_id={creds_in.project_id}")
    validate_organization(session, org_id)
    if not creds_in or not creds_in.provider or not creds_in.credential:
        logger.warning(f"[credential.update] Invalid update payload | org_id={org_id}")
        raise HTTPException(
            status_code=400, detail="Provider and credential must be provided"
        )

    updated_creds = update_creds_for_org(
        session=session, org_id=org_id, creds_in=creds_in
    )

    logger.info(f"[credential.update] Credentials updated | count={len(updated_creds)}, org_id={org_id}, provider={creds_in.provider}")
    return APIResponse.success_response([cred.to_public() for cred in updated_creds])


@router.delete(
    "/{org_id}/{provider}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[dict],
    summary="Delete specific provider credentials for an organization and project",
)
def delete_provider_credential(
    *, session: SessionDep, org_id: int, provider: str, project_id: int | None = None
):
    logger.info(f"[credential.delete_provider] Deleting provider credential | org_id={org_id}, provider={provider}, project_id={project_id}")
    provider_enum = validate_provider(provider)
    if not provider_enum:
        logger.warning(f"[credential.delete_provider] Invalid provider | provider={provider}")
        raise HTTPException(status_code=400, detail="Invalid provider")

    provider_creds = get_provider_credential(
        session=session,
        org_id=org_id,
        provider=provider_enum,
        project_id=project_id,
    )
    if provider_creds is None:
        logger.warning(f"[credential.delete_provider] Credential not found | org_id={org_id}, provider={provider}, project_id={project_id}")
        raise HTTPException(status_code=404, detail="Provider credentials not found")

    updated_creds = remove_provider_credential(
        session=session, org_id=org_id, provider=provider_enum, project_id=project_id
    )

    logger.info(f"[credential.delete_provider] Credential deleted | org_id={org_id}, provider={provider}, project_id={project_id}")
    return APIResponse.success_response(
        {"message": "Provider credentials removed successfully"}
    )


@router.delete(
    "/{org_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[dict],
    summary="Delete all credentials for an organization and project",
    description="Removes all credentials for a specific organization and project combination. If project_id is provided, only removes credentials for that project. This is a soft delete operation that marks credentials as inactive. This endpoint requires superuser privileges.",
)
def delete_all_credentials(
    *, session: SessionDep, org_id: int, project_id: int | None = None
):
    logger.info(f"[credential.delete_all] Deleting all credentials | org_id={org_id}, project_id={project_id}")
    creds = remove_creds_for_org(session=session, org_id=org_id, project_id=project_id)
    if not creds:
        logger.warning(f"[credential.delete_all] No credentials found to delete | org_id={org_id}, project_id={project_id}")
        raise HTTPException(
            status_code=404, detail="Credentials for organization not found"
        )

    logger.info(f"[credential.delete_all] All credentials deleted | org_id={org_id}, project_id={project_id}")
    return APIResponse.success_response({"message": "Credentials deleted successfully"})
