import pytest
from fastapi.testclient import TestClient
from app.main import app  # Assuming your FastAPI app is in app/main.py
from app.models import Organization, Project, User, APIKey
from app.crud import create_organization, create_project, create_user, create_api_key
from app.api.deps import SessionDep
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel
from app.core.config import settings
from app.tests.utils.utils import random_email, random_lower_string

client = TestClient(app)


# Test for onboarding a new user
def test_onboard_user(client, db: Session, superuser_token_headers: dict[str, str]):
    # Prepare the test data
    data = {
        "organization_name": "TestOrg",
        "project_name": "TestProject",
        "email": random_email(),
        "password": "testpassword123",
        "user_name": "Test User",
    }

    # Send the POST request to the /onboard endpoint
    response = client.post(
        f"{settings.API_V1_STR}/onboard", json=data, headers=superuser_token_headers
    )

    # Assert the response status code is 200
    assert response.status_code == 200

    # Assert the response contains the correct data
    response_data = response.json()
    assert "organization_id" in response_data
    assert "project_id" in response_data
    assert "user_id" in response_data
    assert "api_key" in response_data

    # Verify the organization, project, and user were created
    organization = (
        db.query(Organization)
        .filter(Organization.name == data["organization_name"])
        .first()
    )
    project = db.query(Project).filter(Project.name == data["project_name"]).first()
    user = db.query(User).filter(User.email == data["email"]).first()
    api_key = db.query(APIKey).filter(APIKey.user_id == user.id).first()

    # Assert the organization, project, and user were created
    assert organization is not None
    assert project is not None
    assert user is not None
    assert api_key is not None

    # Assert the API key is correct
    assert api_key.key == response_data["api_key"]

    # Assert that the user's is_superuser flag is False
    assert user.is_superuser is False


# Test for the case when the user already exists
def test_create_user_existing_email(
    client, db: Session, superuser_token_headers: dict[str, str]
):
    data = {
        "organization_name": "TestOrg",
        "project_name": "TestProject",
        "email": random_email(),
        "password": "testpassword123",
        "user_name": "Test User",
    }

    # Create a user to simulate an existing user
    client.post(
        f"{settings.API_V1_STR}/onboard", json=data, headers=superuser_token_headers
    )

    # Try to create a user with the same email (should fail)
    response = client.post(
        f"{settings.API_V1_STR}/onboard", json=data, headers=superuser_token_headers
    )

    # Assert the response status code is 400 (bad request) since the user already exists
    assert response.status_code == 400
    assert response.json()["detail"] == "400: User already exists with this email"


# Test for ensuring the is_superuser flag is false for a new user
def test_is_superuser_flag(
    client, db: Session, superuser_token_headers: dict[str, str]
):
    # Prepare the test data
    data = {
        "organization_name": "TestOrg",
        "project_name": "TestProject",
        "email": random_email(),
        "password": "testpassword123",
        "user_name": "Test User",
    }

    # Send the POST request to the /onboard endpoint
    response = client.post(
        f"{settings.API_V1_STR}/onboard", json=data, headers=superuser_token_headers
    )

    # Assert the response status code is 200
    assert response.status_code == 200

    # Verify the user is created and the is_superuser flag is False
    response_data = response.json()
    user = db.query(User).filter(User.id == response_data["user_id"]).first()
    assert user is not None
    assert user.is_superuser is False


# Test for organization and project creation
def test_organization_and_project_creation(
    client, db: Session, superuser_token_headers: dict[str, str]
):
    data = {
        "organization_name": "NewOrg",
        "project_name": "NewProject",
        "email": random_email(),
        "password": "newpassword123",
        "user_name": "New User",
    }

    # Send the POST request to the /onboard endpoint
    response = client.post(
        f"{settings.API_V1_STR}/onboard", json=data, headers=superuser_token_headers
    )

    # Assert the response status code is 200
    assert response.status_code == 200

    # Assert that the organization and project were created
    organization = (
        db.query(Organization)
        .filter(Organization.name == data["organization_name"])
        .first()
    )
    project = db.query(Project).filter(Project.name == data["project_name"]).first()

    assert organization is not None
    assert project is not None
