from fastapi.testclient import TestClient
from app.main import app  # Assuming your FastAPI app is in app/main.py
from app.models import Organization, Project, User, APIKey
from app.crud import create_organization, create_project, create_user, create_api_key
from sqlalchemy import create_engine
from sqlmodel import Session
from app.core.config import settings
from app.tests.utils.utils import random_email, random_lower_string
from app.core.security import decrypt_api_key

client = TestClient(app)


def test_onboard_user(client, db: Session, superuser_token_headers: dict[str, str]):
    data = {
        "organization_name": "TestOrg",
        "project_name": "TestProject",
        "email": random_email(),
        "password": "testpassword123",
        "user_name": "test_user",
    }

    response = client.post(
        f"{settings.API_V1_STR}/onboard", json=data, headers=superuser_token_headers
    )

    assert response.status_code == 200

    response_data = response.json()
    assert "organization_id" in response_data
    assert "project_id" in response_data
    assert "user_id" in response_data
    assert "api_key" in response_data

    organization = (
        db.query(Organization)
        .filter(Organization.name == data["organization_name"])
        .first()
    )
    project = db.query(Project).filter(Project.name == data["project_name"]).first()
    user = db.query(User).filter(User.email == data["email"]).first()
    api_key = db.query(APIKey).filter(APIKey.user_id == user.id).first()

    assert organization is not None
    assert project is not None
    assert user is not None
    assert api_key is not None

    plain_token = response_data["api_key"]
    encrypted_stored = api_key.key

    assert decrypt_api_key(encrypted_stored) == plain_token  # main check
    assert encrypted_stored != plain_token

    assert user.is_superuser is False


def test_create_user_existing_email(
    client, db: Session, superuser_token_headers: dict[str, str]
):
    data = {
        "organization_name": "TestOrg",
        "project_name": "TestProject",
        "email": random_email(),
        "password": "testpassword123",
        "user_name": "test_user",
    }

    client.post(
        f"{settings.API_V1_STR}/onboard", json=data, headers=superuser_token_headers
    )

    response = client.post(
        f"{settings.API_V1_STR}/onboard", json=data, headers=superuser_token_headers
    )
    assert response.status_code == 400
    assert (
        response.json()["error"] == "API key already exists for this user and project."
    )


def test_is_superuser_flag(
    client, db: Session, superuser_token_headers: dict[str, str]
):
    data = {
        "organization_name": "TestOrg",
        "project_name": "TestProjects",
        "email": random_email(),
        "password": "testpassword123",
        "user_name": "test_user",
    }

    response = client.post(
        f"{settings.API_V1_STR}/onboard", json=data, headers=superuser_token_headers
    )

    assert response.status_code == 200

    response_data = response.json()
    user = db.query(User).filter(User.id == response_data["user_id"]).first()
    assert user is not None
    assert user.is_superuser is False


def test_organization_and_project_creation(
    client, db: Session, superuser_token_headers: dict[str, str]
):
    data = {
        "organization_name": "NewOrg",
        "project_name": "NewProject",
        "email": random_email(),
        "password": "newpassword123",
        "user_name": "new_user",
    }

    response = client.post(
        f"{settings.API_V1_STR}/onboard", json=data, headers=superuser_token_headers
    )

    assert response.status_code == 200

    organization = (
        db.query(Organization)
        .filter(Organization.name == data["organization_name"])
        .first()
    )
    project = db.query(Project).filter(Project.name == data["project_name"]).first()

    assert organization is not None
    assert project is not None
