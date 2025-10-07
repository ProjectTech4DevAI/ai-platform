from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.tests.utils.auth import TestAuthContext
from app.tests.utils.test_data import create_test_api_key, create_test_project
from app.tests.utils.user import create_random_user


def test_create_api_key_as_superuser(
    db: Session,
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Test creating an API key as a superuser."""

    user = create_random_user(db)
    project = create_test_project(db)

    response = client.post(
        f"{settings.API_V1_STR}/apikeys/",
        headers=superuser_token_headers,
        params={
            "project_id": project.id,
            "user_id": user.id,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    assert "key" in data["data"]
    assert "id" in data["data"]
    assert "key_prefix" in data["data"]
    assert data["data"]["project_id"] == project.id
    assert data["data"]["user_id"] == user.id
    assert data["data"]["organization_id"] == project.organization_id
    assert data["data"]["key"].startswith("ApiKey ")


def test_create_api_key_as_normal_user_forbidden(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    user_api_key: TestAuthContext,
) -> None:
    """Test that normal users cannot create API keys (superuser only)."""
    response = client.post(
        f"{settings.API_V1_STR}/apikeys/",
        headers=normal_user_token_headers,
        params={
            "project_id": user_api_key.project_id,
            "user_id": user_api_key.user_id,
        },
    )
    assert response.status_code == 403


def test_list_api_keys(
    db: Session,
    client: TestClient,
    user_api_key: TestAuthContext,
) -> None:
    """Test listing API keys as a normal user."""
    created_keys = []
    for _ in range(3):
        key = create_test_api_key(
            db=db,
            project_id=user_api_key.project_id,
            user_id=user_api_key.user_id,
        )
        created_keys.append(key)

    response = client.get(
        f"{settings.API_V1_STR}/apikeys/",
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    # Verify we have at least the 3 created keys + the fixture key (4 total)
    assert len(data["data"]) >= 4


def test_delete_api_key(
    client: TestClient,
    user_api_key: TestAuthContext,
) -> None:
    """Test deleting an API key by its owner."""

    delete_response = client.delete(
        f"{settings.API_V1_STR}/apikeys/{user_api_key.api_key_id}",
        headers={"X-API-KEY": user_api_key.key},
    )
    assert delete_response.status_code == 200
    data = delete_response.json()
    assert data["success"] is True
    assert "message" in data["data"]
    assert "deleted successfully" in data["data"]["message"].lower()


def test_delete_api_key_nonexistent(
    client: TestClient,
    user_api_key: TestAuthContext,
) -> None:
    """Test deleting a non-existent API key."""
    fake_uuid = uuid4()
    response = client.delete(
        f"{settings.API_V1_STR}/apikeys/{fake_uuid}",
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response.status_code == 404
