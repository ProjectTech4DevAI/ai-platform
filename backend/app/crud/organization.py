from typing import Any, Optional
from datetime import datetime, timezone
from sqlmodel import Session, select
from fastapi import HTTPException

from app.models import Organization, OrganizationCreate
from app.core.util import now


def create_organization(
    *, session: Session, org_create: OrganizationCreate
) -> Organization:
    db_org = Organization.model_validate(org_create)
    db_org.inserted_at = now()
    db_org.updated_at = now()
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
        raise HTTPException(404, "Organization not found")

    if not organization.is_active:
        raise HTTPException("Organization is not active")

    return organization
