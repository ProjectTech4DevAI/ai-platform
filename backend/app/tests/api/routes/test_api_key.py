import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.crud import api_key as api_key_crud
from app.main import app
from app.models import Organization, User
from app.tests.utils.utils import random_email

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


def test_create_api_key(db: Session, superuser_token_headers: dict[str, str]):
    user = create_test_user(db)
    org = create_test_organization(db)

    response = client.post(
        f"{settings.API_V1_STR}/apikeys",
        params={"organization_id": org.id, "user_id": user.id},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "id" in data["data"]
    assert "key" in data["data"]
    assert data["data"]["organization_id"] == org.id
    assert data["data"]["user_id"] == str(user.id)


def test_create_duplicate_api_key(db: Session, superuser_token_headers: dict[str, str]):
    user = create_test_user(db)
    org = create_test_organization(db)

    client.post(
        f"{settings.API_V1_STR}/apikeys",
        params={"organization_id": org.id, "user_id": user.id},
        headers=superuser_token_headers,
    )
    response = client.post(
        f"{settings.API_V1_STR}/apikeys",
        params={"organization_id": org.id, "user_id": user.id},
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert "API Key already exists" in response.json()["detail"]


def test_list_api_keys(db: Session, superuser_token_headers: dict[str, str]):
    user = create_test_user(db)
    org = create_test_organization(db)
    api_key = api_key_crud.create_api_key(db, organization_id=org.id, user_id=user.id)

    response = client.get(
        f"{settings.API_V1_STR}/apikeys",
        params={"organization_id": org.id, "user_id": user.id},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    assert len(data["data"]) > 0
    assert data["data"][0]["organization_id"] == org.id
    assert data["data"][0]["user_id"] == str(user.id)


def test_get_api_key(db: Session, superuser_token_headers: dict[str, str]):
    user = create_test_user(db)
    org = create_test_organization(db)
    api_key = api_key_crud.create_api_key(db, organization_id=org.id, user_id=user.id)

    response = client.get(
        f"{settings.API_V1_STR}/apikeys/{api_key.id}",
        params={"organization_id": api_key.organization_id, "user_id": user.id},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == api_key.id
    assert data["data"]["organization_id"] == api_key.organization_id
    assert data["data"]["user_id"] == str(user.id)


def test_get_nonexistent_api_key(db: Session, superuser_token_headers: dict[str, str]):
    user = create_test_user(db)
    org = create_test_organization(db)

    response = client.get(
        f"{settings.API_V1_STR}/apikeys/999999",
        params={"organization_id": org.id, "user_id": user.id},
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert "API Key does not exist" in response.json()["detail"]


def test_revoke_api_key(db: Session, superuser_token_headers: dict[str, str]):
    user = create_test_user(db)
    org = create_test_organization(db)
    api_key = api_key_crud.create_api_key(db, organization_id=org.id, user_id=user.id)

    response = client.delete(
        f"{settings.API_V1_STR}/apikeys/{api_key.id}",
        params={"organization_id": api_key.organization_id, "user_id": user.id},
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
        params={"organization_id": org.id, "user_id": user.id},
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert "API key not found or already deleted" in response.json()["detail"]
