import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import select

from app.models import (
    Organization,
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationPublic,
)
from app.api.deps import (
    SessionDep,
    get_current_active_superuser,
)
from app.crud.organization import create_organization, get_organization_by_id
from app.utils import APIResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/organizations", tags=["organizations"])


# Retrieve organizations
@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[List[OrganizationPublic]],
)
def read_organizations(session: SessionDep, skip: int = 0, limit: int = 100):
    logger.info(
        f"[organization.list] Listing organizations | skip={skip}, limit={limit}"
    )

    count_statement = select(func.count()).select_from(Organization)
    count = session.exec(count_statement).one()

    statement = select(Organization).offset(skip).limit(limit)
    organizations = session.exec(statement).all()

    logger.info(
        f"[organization.list] {len(organizations)} organization(s) retrieved out of {count}"
    )
    return APIResponse.success_response(organizations)


# Create a new organization
@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[OrganizationPublic],
)
def create_new_organization(*, session: SessionDep, org_in: OrganizationCreate):
    logger.info(f"[organization.create] Creating organization | name={org_in.name}")

    new_org = create_organization(session=session, org_create=org_in)

    logger.info(
        f"[organization.create] Organization created successfully | id={new_org.id}"
    )
    return APIResponse.success_response(new_org)


# Retrieve a specific organization
@router.get(
    "/{org_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[OrganizationPublic],
)
def read_organization(*, session: SessionDep, org_id: int):
    logger.info(f"[organization.read] Fetching organization | id={org_id}")

    org = get_organization_by_id(session=session, org_id=org_id)
    if org is None:
        logger.warning(f"[organization.read] Organization not found | id={org_id}")
        raise HTTPException(status_code=404, detail="Organization not found")

    logger.info(f"[organization.read] Organization fetched successfully | id={org_id}")
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
    logger.info(f"[organization.update] Updating organization | id={org_id}")

    org = get_organization_by_id(session=session, org_id=org_id)
    if org is None:
        logger.warning(f"[organization.update] Organization not found | id={org_id}")
        raise HTTPException(status_code=404, detail="Organization not found")

    org_data = org_in.model_dump(exclude_unset=True)
    org = org.model_copy(update=org_data)

    session.add(org)
    session.commit()
    session.flush()

    logger.info(
        f"[organization.update] Organization updated successfully | id={org_id}"
    )
    return APIResponse.success_response(org)


# Delete an organization
@router.delete(
    "/{org_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[None],
    include_in_schema=False,
)
def delete_organization(session: SessionDep, org_id: int):
    logger.info(f"[organization.delete] Deleting organization | id={org_id}")

    org = get_organization_by_id(session=session, org_id=org_id)
    if org is None:
        logger.warning(f"[organization.delete] Organization not found | id={org_id}")
        raise HTTPException(status_code=404, detail="Organization not found")

    session.delete(org)
    session.commit()

    logger.info(
        f"[organization.delete] Organization deleted successfully | id={org_id}"
    )
    return APIResponse.success_response(None)
