from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Organization, OrganizationCreate, OrganizationUpdate, OrganizationPublic
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from app.crud.organization import create_organization, get_organization_by_id
from app.responses import APIResponse 

router = APIRouter(prefix="/organizations", tags=["organizations"])


# Retrieve organizations
@router.get("/", dependencies=[Depends(get_current_active_superuser)], response_model=APIResponse[List[OrganizationPublic]])
def read_organizations(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    count_statement = select(func.count()).select_from(Organization)
    count = session.exec(count_statement).one()

    statement = select(Organization).offset(skip).limit(limit)
    organizations = session.exec(statement).all()

    return APIResponse.success_response(organizations)


# Create a new organization
@router.post("/", dependencies=[Depends(get_current_active_superuser)], response_model=APIResponse[OrganizationPublic])
def create_new_organization(*, session: SessionDep, org_in: OrganizationCreate) -> Any:
    new_org = create_organization(session=session, org_create=org_in)
    return APIResponse.success_response(new_org)


@router.get("/{org_id}", dependencies=[Depends(get_current_active_superuser)], response_model=APIResponse[OrganizationPublic])
def read_organization(*, session: SessionDep, org_id: int) -> Any:
    """
    Retrieve an organization by ID.
    """
    org = get_organization_by_id(session=session, org_id=org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return APIResponse.success_response(org)


# Update an organization
@router.patch("/{org_id}", dependencies=[Depends(get_current_active_superuser)], response_model=APIResponse[OrganizationPublic])
def update_organization(*, session: SessionDep, org_id: int, org_in: OrganizationUpdate) -> Any:
    org = get_organization_by_id(session=session, org_id=org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    org_data = org_in.model_dump(exclude_unset=True)
    org = org.model_copy(update=org_data)


    session.add(org)
    session.commit()
    session.refresh(org)

    return APIResponse.success_response(org)


# Delete an organization
@router.delete("/{org_id}", dependencies=[Depends(get_current_active_superuser)], response_model=APIResponse[None])
def delete_organization(session: SessionDep, org_id: int) -> Any:
    org = get_organization_by_id(session=session, org_id=org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    session.delete(org)
    session.commit()

    return APIResponse.success_response(None)
