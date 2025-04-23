from typing import Any, Optional
from datetime import datetime

from sqlmodel import Session, select

from app.models import Organization, OrganizationCreate, OrganizationUpdate


def create_organization(
    *, session: Session, org_create: OrganizationCreate
) -> Organization:
    db_org = Organization.model_validate(org_create)
    # Set timestamps
    db_org.inserted_at = datetime.utcnow()
    db_org.updated_at = datetime.utcnow()
    session.add(db_org)
    session.commit()
    session.refresh(db_org)
    return db_org


# Get organization by ID
def get_organization_by_id(session: Session, org_id: int) -> Optional[Organization]:
    statement = select(Organization).where(Organization.id == org_id)
    return session.exec(statement).first()


def get_organization_by_name(*, session: Session, name: str) -> Optional[Organization]:
    statement = select(Organization).where(Organization.name == name)
    return session.exec(statement).first()


# Validate if organization exists and is active
def validate_organization(session: Session, org_id: int) -> Organization:
    """
    Ensures that an organization exists and is active.
    """
    organization = get_organization_by_id(session, org_id)
    if not organization:
        raise ValueError("Organization not found")

    if not organization.is_active:
        raise ValueError("Organization is not active")

    return organization


def update_organization(
    *, session: Session, organization: Organization, org_in: OrganizationUpdate
) -> Organization:
    org_data = org_in.model_dump(exclude_unset=True)
    for key, value in org_data.items():
        setattr(organization, key, value)
    # Update the updated_at timestamp
    organization.updated_at = datetime.utcnow()
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization


def delete_organization(
    *, session: Session, organization: Organization
) -> Organization:
    organization.is_deleted = True
    organization.deleted_at = datetime.utcnow()
    organization.updated_at = datetime.utcnow()
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization
