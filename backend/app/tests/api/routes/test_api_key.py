from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import app
from app.models import APIKey
from app.core.config import settings
from app.tests.utils.utils import get_non_existent_id
from app.tests.utils.user import create_random_user
from app.tests.utils.test_data import create_test_api_key, create_test_project

client = TestClient(app)


def test_create_api_key(db: Session, superuser_token_headers: dict[str, str]):
    user = create_random_user(db)
    project = create_test_project(db)

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
    assert data["data"]["organization_id"] == project.organization_id
    assert data["data"]["user_id"] == user.id


def test_create_duplicate_api_key(db: Session, superuser_token_headers: dict[str, str]):
    user = create_random_user(db)
    project = create_test_project(db)

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
    api_key = create_test_api_key(db)

    response = client.get(
        f"{settings.API_V1_STR}/apikeys",
        params={"project_id": api_key.project_id},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    assert len(data["data"]) > 0

    first_key = data["data"][0]
    assert first_key["organization_id"] == api_key.organization_id
    assert first_key["user_id"] == api_key.user_id


def test_get_api_key(db: Session, superuser_token_headers: dict[str, str]):
    api_key = create_test_api_key(db)

    response = client.get(
        f"{settings.API_V1_STR}/apikeys/{api_key.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == api_key.id
    assert data["data"]["organization_id"] == api_key.organization_id
    assert data["data"]["user_id"] == api_key.user_id


def test_get_nonexistent_api_key(db: Session, superuser_token_headers: dict[str, str]):
    api_key_id = get_non_existent_id(db, APIKey)
    response = client.get(
        f"{settings.API_V1_STR}/apikeys/{api_key_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert "API Key does not exist" in response.json()["error"]


def test_revoke_api_key(db: Session, superuser_token_headers: dict[str, str]):
    api_key = create_test_api_key(db)

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
    api_key_id = get_non_existent_id(db, APIKey)

    response = client.delete(
        f"{settings.API_V1_STR}/apikeys/{api_key_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert "API key not found or already deleted" in response.json()["error"]
