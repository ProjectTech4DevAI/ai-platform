import logging
from typing import Any, Optional
from datetime import datetime, timezone
from sqlmodel import Session, select
from fastapi import HTTPException

from app.models import Organization, OrganizationCreate
from app.core.util import now

logger = logging.getLogger(__name__)


def create_organization(
    *, session: Session, org_create: OrganizationCreate
) -> Organization:
    logger.info(
        f"[create_organization] Starting organization creation | {{'name': '{org_create.name}'}}"
    )
    db_org = Organization.model_validate(org_create)
    db_org.inserted_at = now()
    db_org.updated_at = now()
    session.add(db_org)
    session.commit()
    session.refresh(db_org)
    logger.info(
        f"[create_organization] Organization created successfully | {{'org_id': {db_org.id}, 'name': '{db_org.name}'}}"
    )
    return db_org


# Get organization by ID
def get_organization_by_id(session: Session, org_id: int) -> Optional[Organization]:
    logger.info(
        f"[get_organization_by_id] Retrieving organization | {{'org_id': {org_id}}}"
    )
    statement = select(Organization).where(Organization.id == org_id)
    organization = session.exec(statement).first()
    if organization:
        logger.info(
            f"[get_organization_by_id] Organization retrieved successfully | {{'org_id': {org_id}, 'name': '{organization.name}'}}"
        )
    else:
        logger.warning(
            f"[get_organization_by_id] Organization not found | {{'org_id': {org_id}}}"
        )
    return organization


def get_organization_by_name(*, session: Session, name: str) -> Optional[Organization]:
    logger.info(
        f"[get_organization_by_name] Retrieving organization by name | {{'name': '{name}'}}"
    )
    statement = select(Organization).where(Organization.name == name)
    organization = session.exec(statement).first()
    if organization:
        logger.info(
            f"[get_organization_by_name] Organization retrieved successfully | {{'org_id': {organization.id}, 'name': '{name}'}}"
        )
    else:
        logger.warning(
            f"[get_organization_by_name] Organization not found | {{'name': '{name}'}}"
        )
    return organization


# Validate if organization exists and is active
def validate_organization(session: Session, org_id: int) -> Organization:
    """
    Ensures that an organization exists and is active.
    """
    logger.info(
        f"[validate_organization] Validating organization | {{'org_id': {org_id}}}"
    )
    organization = get_organization_by_id(session, org_id)
    if not organization:
        logger.warning(
            f"[validate_organization] Organization not found | {{'org_id': {org_id}}}"
        )
        raise HTTPException(404, "Organization not found")

    if not organization.is_active:
        logger.warning(
            f"[validate_organization] Organization is not active | {{'org_id': {org_id}, 'name': '{organization.name}'}}"
        )
        raise HTTPException(400, "Organization is not active")

    logger.info(
        f"[validate_organization] Organization validated successfully | {{'org_id': {org_id}, 'name': '{organization.name}'}}"
    )
    return organization