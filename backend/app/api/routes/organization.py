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
    CurrentUserOrg,
    SessionDep,
    get_current_active_superuser,
    check_org_access,
)
from app.crud.organization import (
    create_organization,
    get_organization_by_id,
    validate_organization,
)
from app.utils import APIResponse

router = APIRouter(prefix="/organizations", tags=["organizations"])


# Retrieve organizations
@router.get(
    "/",
    response_model=APIResponse[List[OrganizationPublic]],
)
def read_organizations(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    current_user=CurrentUserOrg,
):
    """
    Return all organizations for superuser,
    or only the one associated with the current user.
    """

    if current_user.is_superuser:
        statement = select(Organization).where(Organization.is_deleted == False)
    else:
        if not current_user.organization_id:
            return APIResponse.success_response([])

        statement = select(Organization).where(
            Organization.id == current_user.organization_id,
            Organization.is_deleted == False,
        )

    statement = statement.offset(skip).limit(limit)
    organizations = session.exec(statement).all()

    return APIResponse.success_response(organizations)


# Create a new organization
@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[OrganizationPublic],
)
def create_new_organization(*, session: SessionDep, org_in: OrganizationCreate):
    """
    Creates a new organization, note that only a superuser can create an organization.
    """
    new_org = create_organization(session=session, org_create=org_in)
    return APIResponse.success_response(new_org)


# Retrieve an organization by ID
@router.get(
    "/{org_id}",
    response_model=APIResponse[OrganizationPublic],
)
def read_organization(*, session: SessionDep, org_id: int, _=Depends(check_org_access)):
    """
    Retrieves an organization by ID,
    a normal user can only retrieve the organization(s) associated with their user ID.
    """
    org = validate_organization(session=session, org_id=org_id)
    return APIResponse.success_response(org)


# Update an organization
@router.patch(
    "/{org_id}",
    response_model=APIResponse[OrganizationPublic],
)
def update_organization(
    *,
    session: SessionDep,
    org_id: int,
    org_in: OrganizationUpdate,
    _=Depends(check_org_access),
):
    """
    Updates an organization by ID,
    a normal user can only update the organization(s) associated with their user ID.
    """
    org = validate_organization(session=session, org_id=org_id)

    org_data = org_in.model_dump(exclude_unset=True)
    org = org.model_copy(update=org_data)

    session.add(org)
    session.commit()
    session.flush()

    return APIResponse.success_response(org)


# Delete an organization
@router.delete(
    "/{org_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[None],
    include_in_schema=False,
)
def delete_organization(session: SessionDep, org_id: int):
    """
    Deletes an existing organization, note that only a superuser can delete an organization.
    """
    org = validate_organization(session=session, org_id=org_id)
    session.delete(org)
    session.commit()

    return APIResponse.success_response(None)
