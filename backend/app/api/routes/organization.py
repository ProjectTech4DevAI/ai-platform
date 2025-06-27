from typing import List

from fastapi import APIRouter
from sqlmodel import select

from app.models import (
    Organization,
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationPublic,
)
from app.api.deps import CurrentUserOrg, SessionDep, check_org_access
from app.crud.organization import create_organization, validate_organization
from app.utils import APIResponse


router = APIRouter(prefix="/organizations", tags=["organizations"])


# Retrieve organizations
@router.get("/", response_model=APIResponse[List[OrganizationPublic]])
def read_organizations(
    session: SessionDep, _current_user: CurrentUserOrg, skip: int = 0, limit: int = 100
):
    """Get a list of organizations for the current user."""
    if _current_user.is_superuser:
        statement = select(Organization).offset(skip).limit(limit)
    else:
        statement = (
            select(Organization)
            .where(Organization.id == _current_user.organization_id)
            .offset(skip)
            .limit(limit)
        )
    organizations = session.exec(statement).all()
    return APIResponse.success_response(organizations)


@router.post("/", response_model=APIResponse[OrganizationPublic])
def create_new_organization(
    *, session: SessionDep, _current_user: CurrentUserOrg, org_in: OrganizationCreate
):
    """Create a new organization if allowed."""
    check_org_access(_current_user)
    new_org = create_organization(session=session, org_create=org_in)
    return APIResponse.success_response(new_org)


@router.get("/{org_id}", response_model=APIResponse[OrganizationPublic])
def read_organization(
    *, session: SessionDep, _current_user: CurrentUserOrg, org_id: int
):
    """Read a specific organization by ID."""
    org = validate_organization(session=session, org_id=org_id)
    check_org_access(_current_user, org_id)  # Check access to the organization
    return APIResponse.success_response(org)


@router.patch("/{org_id}", response_model=APIResponse[OrganizationPublic])
def update_organization(
    *,
    session: SessionDep,
    _current_user: CurrentUserOrg,
    org_id: int,
    org_in: OrganizationUpdate,
):
    """Update an existing organization."""
    org = validate_organization(session=session, org_id=org_id)
    check_org_access(_current_user, org_id)  # Check access to the organization

    org_data = org_in.model_dump(exclude_unset=True)
    org = org.model_copy(update=org_data)

    session.add(org)
    session.commit()
    session.flush()

    return APIResponse.success_response(org)


@router.delete("/{org_id}", response_model=APIResponse[None], include_in_schema=False)
def delete_organization(
    session: SessionDep, _current_user: CurrentUserOrg, org_id: int
):
    """Delete an organization."""
    org = validate_organization(session=session, org_id=org_id)
    check_org_access(_current_user, org_id)  # Check access to the organization

    session.delete(org)
    session.commit()

    return APIResponse.success_response(None)
