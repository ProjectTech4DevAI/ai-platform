import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.main import app
from app.models import APIKey, User, Organization, Project
from app.core.config import settings
from app.crud.api_key import create_api_key
from app.tests.utils.utils import random_email
from app.core.security import get_password_hash

client = TestClient(app)


def create_test_user(db: Session) -> User:
    user = User(
        email=random_email(),
        hashed_password=get_password_hash("password123"),
        is_superuser=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_test_organization(db: Session) -> Organization:
    org = Organization(
        name=f"Test Organization {uuid.uuid4()}", description="Test Organization"
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def create_test_project(db: Session, organization_id: int) -> Project:
    project = Project(name="Test Project", organization_id=organization_id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def test_create_api_key(db: Session, superuser_token_headers: dict[str, str]):
    user = create_test_user(db)
    org = create_test_organization(db)
    project = create_test_project(db, organization_id=org.id)

    response = client.post(
        f"{settings.API_V1_STR}/apikeys",
        params={"project_id": project.id, "user_id": user.id},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "id" in data["data"]
    assert "key" in data["data"]
    assert data["data"]["organization_id"] == org.id
    assert data["data"]["user_id"] == user.id


def test_create_duplicate_api_key(db: Session, superuser_token_headers: dict[str, str]):
    user = create_test_user(db)
    org = create_test_organization(db)
    project = create_test_project(db, organization_id=org.id)

    client.post(
        f"{settings.API_V1_STR}/apikeys",
        params={"project_id": project.id, "user_id": user.id},
        headers=superuser_token_headers,
    )
    response = client.post(
        f"{settings.API_V1_STR}/apikeys",
        params={"project_id": project.id, "user_id": user.id},
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert "API Key already exists" in response.json()["error"]


def test_list_api_keys(db: Session, superuser_token_headers: dict[str, str]):
    user = create_test_user(db)
    org = create_test_organization(db)
    project = create_test_project(db, organization_id=org.id)
    api_key = create_api_key(
        db, organization_id=org.id, user_id=user.id, project_id=project.id
    )

    response = client.get(
        f"{settings.API_V1_STR}/apikeys",
        params={"project_id": project.id},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    assert len(data["data"]) > 0

    first_key = data["data"][0]
    assert first_key["organization_id"] == org.id
    assert first_key["user_id"] == user.id


def test_get_api_key(db: Session, superuser_token_headers: dict[str, str]):
    user = create_test_user(db)
    org = create_test_organization(db)
    project = create_test_project(db, organization_id=org.id)
    api_key = create_api_key(
        db, organization_id=org.id, user_id=user.id, project_id=project.id
    )

    response = client.get(
        f"{settings.API_V1_STR}/apikeys/{api_key.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == api_key.id
    assert data["data"]["organization_id"] == api_key.organization_id
    assert data["data"]["user_id"] == user.id


def test_get_nonexistent_api_key(db: Session, superuser_token_headers: dict[str, str]):
    response = client.get(
        f"{settings.API_V1_STR}/apikeys/999999",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert "API Key does not exist" in response.json()["error"]


def test_revoke_api_key(db: Session, superuser_token_headers: dict[str, str]):
    user = create_test_user(db)
    org = create_test_organization(db)
    project = create_test_project(db, organization_id=org.id)
    api_key = create_api_key(
        db, organization_id=org.id, user_id=user.id, project_id=project.id
    )

    response = client.delete(
        f"{settings.API_V1_STR}/apikeys/{api_key.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "API key revoked successfully" in data["data"]["message"]


def test_revoke_nonexistent_api_key(
    db: Session, superuser_token_headers: dict[str, str]
):
    user = create_test_user(db)
    org = create_test_organization(db)

    response = client.delete(
        f"{settings.API_V1_STR}/apikeys/999999",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert "API key not found or already deleted" in response.json()["error"]
