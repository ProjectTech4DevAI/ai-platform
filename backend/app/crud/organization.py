from typing import Any, Optional
from sqlmodel import Session, select
from app.models import Organization, OrganizationCreate


# Create a new organization
def create_organization(*, session: Session, org_create: OrganizationCreate) -> Organization:
    db_org = Organization.model_validate(org_create)
    session.add(db_org)
    session.commit()
    session.refresh(db_org)
    return db_org


# Get organization by ID
def get_organization_by_id(*, session: Session, org_id: int) -> Optional[Organization]:
    statement = select(Organization).where(Organization.id == org_id)
    return session.exec(statement).first()

def get_organization_by_name(*, session: Session, name: str) -> Optional[Organization]:
    statement = select(Organization).where(Organization.name == name)
    return session.exec(statement).first()

