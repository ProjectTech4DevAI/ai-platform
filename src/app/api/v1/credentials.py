from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Request
from fastcrud.paginated import PaginatedListResponse, compute_offset, paginated_response
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import DuplicateValueException, NotFoundException
from ...crud.crud_creds import crud_credentials
from ...crud.crud_org import crud_organizations
from ...crud.crud_projects import crud_projects
from ...schemas.credentials import (
    CredentialsCreateInternal,
    CredentialsRead,
    CredentialsUpdate,
    CredentialsDelete,
)
from ...schemas.organization import OrganizationRead
from ...schemas.project import ProjectRead

router = APIRouter(tags=["credentials"])


# 🚀 Create or Fetch a Credential (Assigns to Organization & Project)
# 🚀 Create or Fetch a Credential (Assigns to Organization & Project)
@router.post("/credential", response_model=CredentialsRead, status_code=201)
async def create_or_get_credential(
    request: Request,
    organization_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],  # ✅ Moved before default params
    secrets: dict[str, str] = {},
    email: str = "user@example.com",
    project_id: Optional[int] = None,
) -> CredentialsRead:
    # Ensure organization exists
    org_row = await crud_organizations.get(
        db=db, id=organization_id, schema_to_select=OrganizationRead
    )
    if not org_row:
        raise NotFoundException("Organization not found")

    # If no project_id provided, use a default project
    if not project_id:
        project_row = await crud_projects.get(
            db=db, organization_id=organization_id, schema_to_select=ProjectRead
        )
        if not project_row:
            raise NotFoundException("No default project found. Please specify a project.")
        project_id = project_row.id

    # Check if credential exists
    cred_row = await crud_credentials.get(
        db=db,
        organization_id=organization_id,
        project_id=project_id,
        email=email,
        schema_to_select=CredentialsRead,
    )
    if cred_row:
        return cred_row

    # Create new credential
    cred_internal = CredentialsCreateInternal(
        organization_id=organization_id, project_id=project_id, secrets=secrets, email=email
    )
    created_cred: CredentialsRead = await crud_credentials.create(db=db, object=cred_internal)
    return created_cred
    # Ensure organization exists
    org_row = await crud_organizations.get(
        db=db, id=organization_id, schema_to_select=OrganizationRead
    )
    if not org_row:
        raise NotFoundException("Organization not found")

    # If no project_id provided, use a default project
    if not project_id:
        project_row = await crud_projects.get(
            db=db, organization_id=organization_id, schema_to_select=ProjectRead
        )
        if not project_row:
            raise NotFoundException("No default project found. Please specify a project.")
        project_id = project_row.id

    # Check if credential exists
    cred_row = await crud_credentials.get(
        db=db,
        organization_id=organization_id,
        project_id=project_id,
        email=email,
        schema_to_select=CredentialsRead,
    )
    if cred_row:
        return cred_row

    # Create new credential
    cred_internal = CredentialsCreateInternal(
        organization_id=organization_id, project_id=project_id, secrets=secrets, email=email
    )
    created_cred: CredentialsRead = await crud_credentials.create(db=db, object=cred_internal)
    return created_cred


# 🚀 List Credentials (Paginated)
@router.get("/credentials", response_model=PaginatedListResponse[CredentialsRead])
async def list_credentials(
    request: Request,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    organization_id: Optional[int] = None,
    project_id: Optional[int] = None,
    page: int = 1,
    items_per_page: int = 10,
) -> dict:
    filter_criteria = {}
    if organization_id:
        filter_criteria["organization_id"] = organization_id
    if project_id:
        filter_criteria["project_id"] = project_id

    creds_data = await crud_credentials.get_multi(
        db=db,
        offset=compute_offset(page, items_per_page),
        limit=items_per_page,
        schema_to_select=CredentialsRead,
        **filter_criteria,
    )

    response: dict[str, Any] = paginated_response(
        crud_data=creds_data, page=page, items_per_page=items_per_page
    )
    return response


# 🚀 Get a Specific Credential
@router.get("/credential/{credential_id}", response_model=CredentialsRead)
async def get_credential(
    request: Request, credential_id: int, db: Annotated[AsyncSession, Depends(async_get_db)]
) -> CredentialsRead:
    cred_row = await crud_credentials.get(db=db, id=credential_id, schema_to_select=CredentialsRead)
    if not cred_row:
        raise NotFoundException("Credential not found")

    return cred_row


# 🚀 Update a Credential (Modify Secrets or Email)
@router.patch("/credential/{credential_id}")
async def update_credential(
    request: Request,
    credential_id: int,
    values: CredentialsUpdate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, str]:
    cred_row = await crud_credentials.get(db=db, id=credential_id, schema_to_select=CredentialsRead)
    if cred_row is None:
        raise NotFoundException("Credential not found")

    await crud_credentials.update(db=db, object=values, id=credential_id)
    return {"message": "Credential updated"}


# 🚀 Soft Delete a Credential
@router.delete("/credential/{credential_id}")
async def delete_credential(
    request: Request,
    credential_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, str]:
    cred_row = await crud_credentials.get(db=db, id=credential_id, schema_to_select=CredentialsRead)
    if not cred_row:
        raise NotFoundException("Credential not found")

    delete_object = CredentialsDelete(is_deleted=True, deleted_at=cred_row.created_at)
    await crud_credentials.update(db=db, object=delete_object, id=credential_id)

    return {"message": "Credential soft deleted"}


# 🚀 Restore a Soft-Deleted Credential
@router.patch("/credential/{credential_id}/restore")
async def restore_credential(
    request: Request,
    credential_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, str]:
    cred_row = await crud_credentials.get(db=db, id=credential_id, schema_to_select=CredentialsRead)
    if not cred_row:
        raise NotFoundException("Credential not found")

    restore_object = CredentialsDelete(is_deleted=False)
    await crud_credentials.update(db=db, object=restore_object, id=credential_id)

    return {"message": "Credential restored"}
