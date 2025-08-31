import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import APIKeyPublic
from app.core.config import settings
from app.core.providers import Provider
from app.models.credentials import Credential
from app.core.security import decrypt_credentials
from app.tests.utils.utils import (
    generate_random_string,
)
from app.tests.utils.test_data import (
    create_test_credential,
    test_credential_data,
)


@pytest.fixture
def create_test_credentials(db: Session):
    return create_test_credential(db)


def test_set_credential(
    client: TestClient,
    user_api_key: APIKeyPublic,
):
    project_id = user_api_key.project_id
    org_id = user_api_key.organization_id

    api_key = "sk-" + generate_random_string(10)
    # Ensure clean state for provider
    client.delete(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )
    credential_data = {
        "organization_id": org_id,
        "project_id": project_id,
        "is_active": True,
        "credential": {
            Provider.OPENAI.value: {
                "api_key": api_key,
                "model": "gpt-4",
                "temperature": 0.7,
            }
        },
    }

    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=credential_data,
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 1

    assert data[0]["organization_id"] == org_id
    assert data[0]["provider"] == Provider.OPENAI.value
    assert data[0]["credential"]["model"] == "gpt-4"


def test_set_credentials_ignored_mismatched_ids(
    client: TestClient,
    user_api_key: APIKeyPublic,
):
    # Even if mismatched IDs are sent, route uses API key context
    # Ensure clean state for provider
    client.delete(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )
    credential_data = {
        "organization_id": 999999,
        "project_id": 999999,
        "is_active": True,
        "credential": {Provider.OPENAI.value: {"api_key": "sk-123", "model": "gpt-4"}},
    }

    response_invalid = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=credential_data,
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response_invalid.status_code == 200


def test_read_credentials_with_creds(
    client: TestClient,
    user_api_key: APIKeyPublic,
):
    # Ensure at least one credential exists for current project
    api_key_value = "sk-" + generate_random_string(10)
    payload = {
        "organization_id": user_api_key.organization_id,
        "project_id": user_api_key.project_id,
        "is_active": True,
        "credential": {
            Provider.OPENAI.value: {"api_key": api_key_value, "model": "gpt-4"}
        },
    }
    client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=payload,
        headers={"X-API-KEY": user_api_key.key},
    )

    response = client.get(
        f"{settings.API_V1_STR}/credentials/",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 1


def test_read_credentials_not_found(
    client: TestClient, db: Session, user_api_key: APIKeyPublic
):
    # Delete all first to ensure none remain
    client.delete(
        f"{settings.API_V1_STR}/credentials/", headers={"X-API-KEY": user_api_key.key}
    )
    response = client.get(
        f"{settings.API_V1_STR}/credentials/",
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response.status_code == 404
    assert "Credentials not found" in response.json()["error"]


def test_read_provider_credential(
    client: TestClient,
    user_api_key: APIKeyPublic,
):
    # Ensure exists
    client.delete(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )
    client.post(
        f"{settings.API_V1_STR}/credentials/",
        json={
            "organization_id": user_api_key.organization_id,
            "project_id": user_api_key.project_id,
            "credential": {
                Provider.OPENAI.value: {"api_key": "sk-xyz", "model": "gpt-4"}
            },
        },
        headers={"X-API-KEY": user_api_key.key},
    )

    response = client.get(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model"] == "gpt-4"
    assert "api_key" in data


def test_read_provider_credential_not_found(
    client: TestClient, db: Session, user_api_key: APIKeyPublic
):
    # Ensure none
    client.delete(
        f"{settings.API_V1_STR}/credentials/", headers={"X-API-KEY": user_api_key.key}
    )
    response = client.get(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "Provider credentials not found"


def test_update_credentials(
    client: TestClient,
    user_api_key: APIKeyPublic,
):
    # Ensure exists
    client.delete(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )
    client.post(
        f"{settings.API_V1_STR}/credentials/",
        json={
            "organization_id": user_api_key.organization_id,
            "project_id": user_api_key.project_id,
            "is_active": True,
            "credential": {
                Provider.OPENAI.value: {"api_key": "sk-abc", "model": "gpt-4"}
            },
        },
        headers={"X-API-KEY": user_api_key.key},
    )

    update_data = {
        "provider": Provider.OPENAI.value,
        "credential": {
            "api_key": "sk-" + generate_random_string(),
            "model": "gpt-4-turbo",
            "temperature": 0.8,
        },
    }

    response = client.patch(
        f"{settings.API_V1_STR}/credentials/",
        json=update_data,
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["provider"] == Provider.OPENAI.value
    assert data[0]["credential"]["model"] == "gpt-4-turbo"
    assert data[0]["updated_at"] is not None


def test_update_credentials_not_found_for_provider(
    client: TestClient, db: Session, user_api_key: APIKeyPublic
):
    # Ensure none exist
    client.delete(
        f"{settings.API_V1_STR}/credentials/", headers={"X-API-KEY": user_api_key.key}
    )

    update_data = {
        "provider": Provider.OPENAI.value,
        "credential": {
            "api_key": "sk-" + generate_random_string(),
            "model": "gpt-4-turbo",
            "temperature": 0.8,
        },
    }

    response_invalid = client.patch(
        f"{settings.API_V1_STR}/credentials/",
        json=update_data,
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response_invalid.status_code == 404
    assert response_invalid.json()["error"] == "Credentials not found for this provider"


def test_delete_provider_credential(
    client: TestClient,
    user_api_key: APIKeyPublic,
):
    # Ensure exists
    client.delete(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )
    client.post(
        f"{settings.API_V1_STR}/credentials/",
        json={
            "organization_id": user_api_key.organization_id,
            "project_id": user_api_key.project_id,
            "is_active": True,
            "credential": {
                Provider.OPENAI.value: {"api_key": "sk-abc", "model": "gpt-4"}
            },
        },
        headers={"X-API-KEY": user_api_key.key},
    )

    client.delete(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )


def test_delete_provider_credential_not_found(
    client: TestClient, db: Session, user_api_key: APIKeyPublic
):
    # Ensure not exists
    client.delete(
        f"{settings.API_V1_STR}/credentials/", headers={"X-API-KEY": user_api_key.key}
    )
    response = client.delete(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "Provider credentials not found"


def test_delete_all_credentials(
    client: TestClient,
    user_api_key: APIKeyPublic,
):
    # Ensure exists
    client.delete(
        f"{settings.API_V1_STR}/credentials/",
        headers={"X-API-KEY": user_api_key.key},
    )
    client.post(
        f"{settings.API_V1_STR}/credentials/",
        json={
            "organization_id": user_api_key.organization_id,
            "project_id": user_api_key.project_id,
            "is_active": True,
            "credential": {
                Provider.OPENAI.value: {"api_key": "sk-abc", "model": "gpt-4"}
            },
        },
        headers={"X-API-KEY": user_api_key.key},
    )
    response = client.delete(
        f"{settings.API_V1_STR}/credentials/",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200  # Expect 200 for successful deletion
    data = response.json()["data"]
    assert data["message"] == "All credentials deleted successfully"

    # Verify the credentials are soft deleted
    response = client.get(
        f"{settings.API_V1_STR}/credentials/",
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response.status_code == 404  # Expect 404 as credentials are soft deleted
    assert response.json()["error"] == "Credentials not found"


def test_delete_all_credentials_not_found(
    client: TestClient, db: Session, user_api_key: APIKeyPublic
):
    # Ensure already deleted
    client.delete(
        f"{settings.API_V1_STR}/credentials/", headers={"X-API-KEY": user_api_key.key}
    )
    response = client.delete(
        f"{settings.API_V1_STR}/credentials/",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 404
    assert "Credentials for organization/project not found" in response.json()["error"]


def test_duplicate_credential_creation(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    credential = test_credential_data(db)
    # Ensure clean state for provider
    client.delete(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )

    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=credential.dict(),
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response.status_code == 200

    # Try to create the same credentials again
    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=credential.dict(),
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response.status_code == 400

    assert "already exist" in response.json()["error"]


def test_multiple_provider_credentials(
    client: TestClient,
    user_api_key: APIKeyPublic,
):
    # Ensure clean state for current org/project
    client.delete(
        f"{settings.API_V1_STR}/credentials/",
        headers={"X-API-KEY": user_api_key.key},
    )

    # Create OpenAI credentials
    openai_credential = {
        "organization_id": user_api_key.organization_id,
        "project_id": user_api_key.project_id,
        "is_active": True,
        "credential": {
            Provider.OPENAI.value: {
                "api_key": "sk-" + generate_random_string(10),
                "model": "gpt-4",
                "temperature": 0.7,
            }
        },
    }

    # Create Langfuse credentials
    langfuse_credential = {
        "organization_id": user_api_key.organization_id,
        "project_id": user_api_key.project_id,
        "is_active": True,
        "credential": {
            Provider.LANGFUSE.value: {
                "secret_key": "sk-" + generate_random_string(10),
                "public_key": "pk-" + generate_random_string(10),
                "host": "https://cloud.langfuse.com",
            }
        },
    }

    # Create both credentials
    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=openai_credential,
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=langfuse_credential,
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response.status_code == 200

    # Fetch all credentials
    response = client.get(
        f"{settings.API_V1_STR}/credentials/",
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2
    providers = [cred["provider"] for cred in data]
    assert Provider.OPENAI.value in providers
    assert Provider.LANGFUSE.value in providers


def test_credential_encryption(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    credential = test_credential_data(db)
    original_api_key = credential.credential[Provider.OPENAI.value]["api_key"]

    # Create credentials
    client.delete(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )
    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=credential.dict(),
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response.status_code == 200

    db_credential = (
        db.query(Credential)
        .filter(
            Credential.organization_id == user_api_key.organization_id,
            Credential.project_id == user_api_key.project_id,
            Credential.is_active == True,
            Credential.provider == Provider.OPENAI.value,
        )
        .first()
    )

    assert db_credential is not None
    # Verify the stored credential is encrypted
    assert db_credential.credential != original_api_key

    # Verify we can decrypt and get the original value
    decrypted_creds = decrypt_credentials(db_credential.credential)
    assert decrypted_creds.get("api_key") == original_api_key


def test_credential_encryption_consistency(
    client: TestClient, db: Session, user_api_key: APIKeyPublic
):
    credentials = test_credential_data(db)
    original_api_key = credentials.credential[Provider.OPENAI.value]["api_key"]

    # Create credentials
    client.delete(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )
    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=credentials.dict(),
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response.status_code == 200

    # Fetch the credentials through the API
    response = client.get(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response.status_code == 200
    data = response.json()["data"]

    # Verify the API returns the decrypted value
    assert data["api_key"] == original_api_key

    # Update the credentials
    new_api_key = "sk-" + generate_random_string(10)
    update_data = {
        "provider": Provider.OPENAI.value,
        "credential": {
            "api_key": new_api_key,
            "model": "gpt-4",
            "temperature": 0.7,
        },
    }

    response = client.patch(
        f"{settings.API_V1_STR}/credentials/",
        json=update_data,
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response.status_code == 200

    response = client.get(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["api_key"] == new_api_key
