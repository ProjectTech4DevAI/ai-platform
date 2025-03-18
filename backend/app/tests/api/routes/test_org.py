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

# Test retrieving organizations
def test_read_organizations(db: Session, superuser_token_headers: dict[str, str]):
    response = client.get(f"{settings.API_V1_STR}/organizations/", headers=superuser_token_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

# Test creating an organization
def test_create_organization(db: Session, superuser_token_headers: dict[str, str]):
        unique_name = f"Org-{random_lower_string()}"
        org_data = {"name": unique_name, "is_active": True}
        response = client.post(
            f"{settings.API_V1_STR}/organizations/", json=org_data, headers=superuser_token_headers
        )
        assert 200 <= response.status_code < 300
        created_org = response.json()
        org = get_organization_by_id(session=db, org_id=created_org["id"])
        assert org
        assert org.name == created_org["name"]

def test_update_organization(db: Session, test_organization: Organization, superuser_token_headers: dict[str, str]):
    unique_name = f"UpdatedOrg-{random_lower_string()}"  # ✅ Ensure a unique name
    update_data = {"name": unique_name, "is_active": False}
    
    response = client.patch(
        f"{settings.API_V1_STR}/organizations/{test_organization.id}",
        json=update_data,
        headers=superuser_token_headers,
    )
    
    assert response.status_code == 200
    updated_org = response.json()
    assert "name" in updated_org
    assert updated_org["name"] == update_data["name"]
    assert "is_active" in updated_org
    assert updated_org["is_active"] == update_data["is_active"]

# Test deleting an organization
def test_delete_organization(db: Session, test_organization: Organization, superuser_token_headers: dict[str, str]):
    response = client.delete(
        f"{settings.API_V1_STR}/organizations/{test_organization.id}", headers=superuser_token_headers
    )
    assert response.status_code == 200
    response = client.get(f"{settings.API_V1_STR}/organizations/{test_organization.id}", headers=superuser_token_headers)
    assert response.status_code == 404
 