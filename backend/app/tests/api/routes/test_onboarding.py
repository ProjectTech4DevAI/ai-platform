from fastapi.testclient import TestClient
from sqlmodel import Session

from app.utils import mask_string
from app.core.config import settings
from app.tests.utils.utils import random_email, random_lower_string
from app.tests.utils.test_data import create_test_organization


def test_onboard_project_new_organization_project_user(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test onboarding with new organization, project, and user."""
    org_name = "TestOrgOnboard"
    project_name = "TestProjectOnboard"
    email = random_email()
    password = random_lower_string()
    user_name = "Test User Onboard"
    openai_key = f"sk-{random_lower_string()}"

    onboard_data = {
        "organization_name": org_name,
        "project_name": project_name,
        "email": email,
        "password": password,
        "user_name": user_name,
        "openai_api_key": openai_key,
    }

    response = client.post(
        f"{settings.API_V1_STR}/onboard",
        json=onboard_data,
        headers=superuser_token_headers,
    )

    assert response.status_code == 201
    response_data = response.json()

    # Check the response structure
    assert "data" in response_data
    assert "success" in response_data
    assert response_data["success"] is True

    data = response_data["data"]
    assert data["organization_name"] == org_name
    assert data["project_name"] == project_name
    assert data["user_email"] == email
    assert "api_key" in data
    assert len(data["api_key"]) > 0
    assert "organization_id" in data
    assert "project_id" in data
    assert "user_id" in data


def test_onboard_project_existing_organization(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test onboarding with existing organization but new project and user."""
    # Create existing organization
    existing_org = create_test_organization(db)

    project_name = "TestProjectOnboard"
    email = random_email()
    password = random_lower_string()
    user_name = "Test User Onboard"

    onboard_data = {
        "organization_name": existing_org.name,
        "project_name": project_name,
        "email": email,
        "password": password,
        "user_name": user_name,
    }

    response = client.post(
        f"{settings.API_V1_STR}/onboard",
        json=onboard_data,
        headers=superuser_token_headers,
    )

    assert response.status_code == 201
    response_data = response.json()

    data = response_data["data"]
    assert data["organization_id"] == existing_org.id
    assert data["organization_name"] == existing_org.name
    assert data["project_name"] == project_name
    assert data["user_email"] == email


def test_onboard_project_duplicate_project_in_organization(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test onboarding fails when project already exists in the organization."""
    org_name = "TestOrgOnboard"
    project_name = "TestProjectOnboard"
    email = random_email()
    password = random_lower_string()

    onboard_data = {
        "organization_name": org_name,
        "project_name": project_name,
        "email": email,
        "password": password,
    }

    # First request should succeed
    response = client.post(
        f"{settings.API_V1_STR}/onboard",
        json=onboard_data,
        headers=superuser_token_headers,
    )
    assert response.status_code == 201

    # Second request with same org and project should fail
    email2 = random_email()
    onboard_data["email"] = email2

    response = client.post(
        f"{settings.API_V1_STR}/onboard",
        json=onboard_data,
        headers=superuser_token_headers,
    )

    assert response.status_code == 409
    error_response = response.json()
    assert "error" in error_response
    assert "Project already exists" in error_response["error"]


def test_onboard_project_with_auto_generated_defaults(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test onboarding with minimal input using auto-generated defaults."""
    org_name = "TestOrgOnboard"
    project_name = "TestProjectOnboard"

    # Only provide required fields
    onboard_data = {
        "organization_name": org_name,
        "project_name": project_name,
        # email, password, user_name will be auto-generated
    }

    response = client.post(
        f"{settings.API_V1_STR}/onboard",
        json=onboard_data,
        headers=superuser_token_headers,
    )

    assert response.status_code == 201
    response_data = response.json()

    data = response_data["data"]
    assert data["organization_name"] == org_name
    assert data["project_name"] == project_name
    assert data["user_email"] is not None
    assert "@kaapi.org" in data["user_email"]
    assert "api_key" in data
    assert len(data["api_key"]) > 0
