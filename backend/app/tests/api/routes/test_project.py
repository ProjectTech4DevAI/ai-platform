import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.core.security import decrypt_api_key, verify_password

from app.main import app
from app.core.config import settings
from app.models import Project, ProjectCreate, ProjectUpdate
from app.models import Organization, OrganizationCreate, ProjectUpdate
from app.api.deps import get_db
from app.tests.utils.utils import random_lower_string, random_email
from app.crud.project import create_project, get_project_by_id
from app.crud.organization import create_organization
from app.crud import api_key as api_key_crud

client = TestClient(app)


@pytest.fixture
def test_project(db: Session, superuser_token_headers: dict[str, str]):
    unique_org_name = f"TestOrg-{random_lower_string()}"
    org_data = OrganizationCreate(name=unique_org_name, is_active=True)
    organization = create_organization(session=db, org_create=org_data)
    db.commit()

    unique_project_name = f"TestProject-{random_lower_string()}"
    project_description = "This is a test project description."
    project_data = ProjectCreate(
        name=unique_project_name,
        description=project_description,
        is_active=True,
        organization_id=organization.id,
    )
    project = create_project(session=db, project_create=project_data)
    db.commit()

    return project


# Test retrieving projects
def test_read_projects(db: Session, superuser_token_headers: dict[str, str]):
    response = client.get(
        f"{settings.API_V1_STR}/projects/", headers=superuser_token_headers
    )
    assert response.status_code == 200
    response_data = response.json()
    assert "data" in response_data
    assert isinstance(response_data["data"], list)


# Test creating a project
def test_create_new_project(db: Session, superuser_token_headers: dict[str, str]):
    unique_org_name = f"TestOrg-{random_lower_string()}"
    org_data = OrganizationCreate(name=unique_org_name, is_active=True)
    organization = create_organization(session=db, org_create=org_data)
    db.commit()

    unique_project_name = f"TestProject-{random_lower_string()}"
    project_description = "This is a test project description."
    project_data = ProjectCreate(
        name=unique_project_name,
        description=project_description,
        is_active=True,
        organization_id=organization.id,
    )

    response = client.post(
        f"{settings.API_V1_STR}/projects/",
        json=project_data.dict(),
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    created_project = response.json()

    # Adjusted for a nested structure, if needed
    assert "data" in created_project  # Check if response contains a 'data' field
    assert (
        created_project["data"]["name"] == unique_project_name
    )  # Now checking 'name' inside 'data'
    assert created_project["data"]["description"] == project_description
    assert created_project["data"]["organization_id"] == organization.id


# Test updating a project
def test_update_project(
    db: Session, test_project: Project, superuser_token_headers: dict[str, str]
):
    update_data = {"name": "Updated Project Name", "is_active": False}

    response = client.patch(
        f"{settings.API_V1_STR}/projects/{test_project.id}",
        json=update_data,
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    updated_project = response.json()["data"]
    assert "name" in updated_project
    assert updated_project["name"] == update_data["name"]
    assert "is_active" in updated_project
    assert updated_project["is_active"] == update_data["is_active"]


# Test deleting a project
def test_delete_project(
    db: Session, test_project: Project, superuser_token_headers: dict[str, str]
):
    response = client.delete(
        f"{settings.API_V1_STR}/projects/{test_project.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    response = client.get(
        f"{settings.API_V1_STR}/projects/{test_project.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
