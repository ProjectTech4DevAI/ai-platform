from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import (
    Organization,
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationPublic,
)
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from app.crud.organization import (
    create_organization,
    get_organization_by_id,
    update_organization,
    delete_organization,
)
from app.utils import APIResponse

router = APIRouter(prefix="/organizations", tags=["organizations"])


# Retrieve organizations
@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[List[OrganizationPublic]],
)
def read_organizations(session: SessionDep, skip: int = 0, limit: int = 100):
    count_statement = select(func.count()).select_from(Organization)
    count = session.exec(count_statement).one()

    statement = select(Organization).offset(skip).limit(limit)
    organizations = session.exec(statement).all()

    return APIResponse.success_response(organizations)


# Create a new organization
@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[OrganizationPublic],
)
def create_new_organization(*, session: SessionDep, org_in: OrganizationCreate):
    new_org = create_organization(session=session, org_create=org_in)
    return APIResponse.success_response(new_org)


@router.get(
    "/{org_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[OrganizationPublic],
)
def read_organization(*, session: SessionDep, org_id: int):
    """
    Retrieve an organization by ID.
    """
    org = get_organization_by_id(session=session, org_id=org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return APIResponse.success_response(org)


# Update an organization
@router.patch(
    "/{org_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[OrganizationPublic],
)
def update_organization(
    *, session: SessionDep, org_id: int, org_in: OrganizationUpdate
):
    org = get_organization_by_id(session=session, org_id=org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    updated_org = update_organization(session=session, organization=org, org_in=org_in)
    return APIResponse.success_response(updated_org)


# Delete an organization
@router.delete(
    "/{org_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[None],
)
def delete_organization(session: SessionDep, org_id: int):
    org = get_organization_by_id(session=session, org_id=org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    delete_organization(session=session, organization=org)
    return APIResponse.success_response(None)
