from sqlmodel import Session

from app.crud.organization import create_organization, get_organization_by_id
from app.models import Organization, OrganizationCreate
from app.tests.utils.utils import random_lower_string, get_non_existent_id


def test_create_organization(db: Session) -> None:
    """Test creating an organization."""
    name = random_lower_string()
    org_in = OrganizationCreate(name=name)
    org = create_organization(session=db, org_create=org_in)

    assert org.name == name
    assert org.id is not None
    assert org.is_active is True  # Default should be active


def test_get_organization_by_id(db: Session) -> None:
    """Test retrieving an organization by ID."""
    name = random_lower_string()
    org_in = OrganizationCreate(name=name)
    org = create_organization(session=db, org_create=org_in)

    fetched_org = get_organization_by_id(session=db, org_id=org.id)
    assert fetched_org
    assert fetched_org.id == org.id
    assert fetched_org.name == org.name


def test_get_non_existent_organization(db: Session) -> None:
    """Test retrieving a non-existent organization should return None."""
    org_id = get_non_existent_id(db, Organization)
    fetched_org = get_organization_by_id(
        session=db, org_id=org_id
    )  # Assuming ID 999 does not exist
    assert fetched_org is None
