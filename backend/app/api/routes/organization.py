from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select
from typing import Any, List

from app.models import Organization, OrganizationCreate, OrganizationUpdate, OrganizationPublic
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from app.crud.organization import create_organization, get_organization_by_id

router = APIRouter(prefix="/organizations", tags=["organizations"])


# Retrieve organizations
@router.get("/",dependencies=[Depends(get_current_active_superuser)], response_model=List[OrganizationPublic])
def read_organizations(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    count_statement = select(func.count()).select_from(Organization)
    count = session.exec(count_statement).one()

    statement = select(Organization).offset(skip).limit(limit)
    organizations = session.exec(statement).all()

    return organizations


# Create a new organization
@router.post("/",dependencies=[Depends(get_current_active_superuser)], response_model=OrganizationPublic)
def create_new_organization(*, session: SessionDep, org_in: OrganizationCreate) -> Any:
    return create_organization(session=session, org_create=org_in)

@router.get("/{org_id}", dependencies=[Depends(get_current_active_superuser)], response_model=OrganizationPublic)
def read_organization(*, session: SessionDep, org_id: int) -> Any:
    """
    Retrieve an organization by ID.
    """
    org = get_organization_by_id(session=session, org_id=org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org

# Update an organization
@router.patch("/{org_id}",dependencies=[Depends(get_current_active_superuser)], response_model=OrganizationPublic)
def update_organization(*, session: SessionDep, org_id: int, org_in: OrganizationUpdate) -> Any:
    org = get_organization_by_id(session=session, org_id=org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    org_data = org_in.model_dump(exclude_unset=True)
    for key, value in org_data.items():
        setattr(org, key, value)

    session.add(org)
    session.commit()
    session.refresh(org)
    return org


# Delete an organization
@router.delete("/{org_id}",dependencies=[Depends(get_current_active_superuser)])
def delete_organization(session: SessionDep, org_id: int) -> None:
    org = get_organization_by_id(session=session, org_id=org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    session.delete(org)
    session.commit()
