from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError

from app.api.deps import SessionDep, get_current_active_superuser
from app.crud.credentials import (
    get_creds_by_org,
    get_provider_credential,
    remove_creds_for_org,
    set_creds_for_org,
    update_creds_for_org,
    remove_provider_credential,
)
from app.models import CredsCreate, CredsPublic, CredsUpdate
from app.models.organization import Organization
from app.models.project import Project
from app.utils import APIResponse
from app.core.providers import validate_provider

router = APIRouter(prefix="/credentials", tags=["credentials"])


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[List[CredsPublic]],
    summary="Create new credentials for an organization and project",
    description="Creates new credentials for a specific organization and project combination. This endpoint requires superuser privileges. Each organization can have different credentials for different providers and projects. Only one credential per provider is allowed per organization-project combination.",
)
def create_new_credential(*, session: SessionDep, creds_in: CredsCreate):
    try:
        # Check if organization exists
        organization = session.get(Organization, creds_in.organization_id)
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Check if project exists if project_id is provided
        if creds_in.project_id:
            project = session.get(Project, creds_in.project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            if project.organization_id != creds_in.organization_id:
                raise HTTPException(
                    status_code=400,
                    detail="Project does not belong to the specified organization",
                )

        # Check for existing credentials for each provider
        for provider in creds_in.credential.keys():
            existing_cred = get_provider_credential(
                session=session,
                org_id=creds_in.organization_id,
                provider=provider,
                project_id=creds_in.project_id,
            )
            if existing_cred:
                raise HTTPException(
                    status_code=400,
                    detail=f"Credentials for provider '{provider}' already exist for this organization and project combination",
                )

        # Create new credentials
        new_creds = set_creds_for_org(session=session, creds_add=creds_in)
        if not new_creds:
            raise HTTPException(status_code=500, detail="Failed to create credentials")
        return APIResponse.success_response(new_creds)
    except ValueError as e:
        if "Unsupported provider" in str(e):
            raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get(
    "/{org_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[List[CredsPublic]],
    summary="Get all credentials for an organization and project",
    description="Retrieves all provider credentials associated with a specific organization and project combination. If project_id is not provided, returns credentials for the organization level. This endpoint requires superuser privileges.",
)
def read_credential(*, session: SessionDep, org_id: int, project_id: int | None = None):
    try:
        creds = get_creds_by_org(session=session, org_id=org_id, project_id=project_id)
        if not creds:
            raise HTTPException(status_code=404, detail="Credentials not found")
        return APIResponse.success_response(creds)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


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
    try:
        provider_enum = validate_provider(provider)
        provider_creds = get_provider_credential(
            session=session,
            org_id=org_id,
            provider=provider_enum,
            project_id=project_id,
        )
        if provider_creds is None:
            raise HTTPException(
                status_code=404, detail="Provider credentials not found"
            )
        return APIResponse.success_response(provider_creds)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.patch(
    "/{org_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[List[CredsPublic]],
    summary="Update organization and project credentials",
    description="Updates credentials for a specific organization and project combination. Can update specific provider credentials or add new providers. If project_id is provided in the update, credentials will be moved to that project. This endpoint requires superuser privileges.",
)
def update_credential(*, session: SessionDep, org_id: int, creds_in: CredsUpdate):
    try:
        if not creds_in or not creds_in.provider or not creds_in.credential:
            raise HTTPException(
                status_code=400, detail="Provider and credential must be provided"
            )
        organization = session.get(Organization, org_id)
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        updated_creds = update_creds_for_org(
            session=session, org_id=org_id, creds_in=creds_in
        )
        if not updated_creds:
            raise HTTPException(status_code=404, detail="Failed to update credentials")
        return APIResponse.success_response(updated_creds)
    except IntegrityError as e:
        if "ForeignKeyViolation" in str(e):
            raise HTTPException(
                status_code=400,
                detail="Invalid organization ID. Ensure the organization exists before updating credentials.",
            )
        raise HTTPException(
            status_code=500, detail=f"An unexpected database error occurred: {str(e)}"
        )
    except ValueError as e:
        if "Unsupported provider" in str(e):
            raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.delete(
    "/{org_id}/{provider}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[dict],
    summary="Delete specific provider credentials for an organization and project",
    description="Removes credentials for a specific provider while keeping other provider credentials intact. If project_id is provided, only removes credentials for that project. This endpoint requires superuser privileges.",
)
def delete_provider_credential(
    *, session: SessionDep, org_id: int, provider: str, project_id: int | None = None
):
    try:
        provider_enum = validate_provider(provider)
        updated_creds = remove_provider_credential(
            session=session,
            org_id=org_id,
            provider=provider_enum,
            project_id=project_id,
        )
        if not updated_creds:
            raise HTTPException(
                status_code=404, detail="Provider credentials not found"
            )
        return APIResponse.success_response(
            {"message": "Provider credentials removed successfully"}
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Provider credentials not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
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
    try:
        creds = remove_creds_for_org(
            session=session, org_id=org_id, project_id=project_id
        )
        if not creds:
            raise HTTPException(
                status_code=404, detail="Credentials for organization not found"
            )
        return APIResponse.success_response(
            {"message": "Credentials deleted successfully"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )
