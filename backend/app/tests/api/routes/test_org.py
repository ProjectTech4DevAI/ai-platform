import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.core.security import verify_password
from app.models import User, UserCreate
from app.tests.utils.utils import random_email, random_lower_string
from app.models import Organization, OrganizationCreate, OrganizationUpdate
from app.api.deps import get_db
from app.main import app
from app.crud.organization import create_organization, get_organization_by_id

client = TestClient(app)


@pytest.fixture
def test_organization(db: Session, superuser_token_headers: dict[str, str]):
    unique_name = f"TestOrg-{random_lower_string()}"
    org_data = OrganizationCreate(name=unique_name, is_active=True)
    organization = create_organization(session=db, org_create=org_data)
    db.commit()
    return organization


@pytest.fixture
def other_organization(db: Session, superuser_token_headers: dict[str, str]):
    unique_name = f"OtherOrg-{random_lower_string()}"
    org_data = OrganizationCreate(name=unique_name, is_active=True)
    organization = create_organization(session=db, org_create=org_data)
    db.commit()
    return organization


# Test retrieving organizations (Superuser - sees all organizations)
def test_read_organizations_as_superuser(
    db: Session,
    superuser_token_headers: dict[str, str],
    test_organization: Organization,
):
    response = client.get(
        f"{settings.API_V1_STR}/organizations/", headers=superuser_token_headers
    )
    assert response.status_code == 200
    response_data = response.json()
    assert "data" in response_data
    assert isinstance(response_data["data"], list)
    assert (
        len(response_data["data"]) > 0
    )  # Ensure that multiple organizations are returned


# Test creating an organization (Superuser)
def test_create_organization_as_superuser(
    db: Session, superuser_token_headers: dict[str, str]
):
    unique_name = f"Org-{random_lower_string()}"
    org_data = {"name": unique_name, "is_active": True}
    response = client.post(
        f"{settings.API_V1_STR}/organizations/",
        json=org_data,
        headers=superuser_token_headers,
    )
    assert 200 <= response.status_code < 300
    created_org = response.json()
    assert "data" in created_org
    created_org_data = created_org["data"]
    org = get_organization_by_id(session=db, org_id=created_org_data["id"])
    assert org is not None
    assert org.name == created_org_data["name"]
    assert org.is_active == created_org_data["is_active"]


def test_update_organization_as_superuser(
    db: Session,
    test_organization: Organization,
    superuser_token_headers: dict[str, str],
):
    unique_name = f"UpdatedOrg-{random_lower_string()}"
    update_data = {"name": unique_name, "is_active": False}

    response = client.patch(
        f"{settings.API_V1_STR}/organizations/{test_organization.id}",
        json=update_data,
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    updated_org = response.json()["data"]
    assert "name" in updated_org
    assert updated_org["name"] == update_data["name"]
    assert "is_active" in updated_org
    assert updated_org["is_active"] == update_data["is_active"]


# Test updating an organization (Regular user - should only update their own)
def test_update_organization_as_regular_user(
    db: Session,
    test_organization: Organization,
    normal_user_token_headers: dict[str, str],
):
    unique_name = f"UpdatedOrg-{random_lower_string()}"
    update_data = {"name": unique_name, "is_active": False}

    # Regular user should only be allowed to update their own organization
    response = client.patch(
        f"{settings.API_V1_STR}/organizations/{test_organization.id}",
        json=update_data,
        headers=normal_user_token_headers,
    )
    assert (
        response.status_code == 403
    )  # Forbidden if trying to update someone else's organization


# Test deleting an organization (Superuser)
def test_delete_organization_as_superuser(
    db: Session,
    test_organization: Organization,
    superuser_token_headers: dict[str, str],
):
    response = client.delete(
        f"{settings.API_V1_STR}/organizations/{test_organization.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    response = client.get(
        f"{settings.API_V1_STR}/organizations/{test_organization.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


# Test deleting an organization (Regular user - should only delete their own)
def test_delete_organization_as_regular_user(
    db: Session,
    test_organization: Organization,
    normal_user_token_headers: dict[str, str],
):
    response = client.delete(
        f"{settings.API_V1_STR}/organizations/{test_organization.id}",
        headers=normal_user_token_headers,
    )
    assert (
        response.status_code == 403
    )  # Forbidden for regular user to delete someone else's org


# Test regular user accessing another organization (should be forbidden)
def test_read_organization_as_regular_user_without_access(
    db: Session,
    normal_user_token_headers: dict[str, str],
    other_organization: Organization,
):
    # Simulate a regular user with no access to another organization
    response = client.get(
        f"{settings.API_V1_STR}/organizations/{other_organization.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403  # Forbidden, as the user doesn't have access
