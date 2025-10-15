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


def test_set_credential(
    client: TestClient,
    user_api_key: APIKeyPublic,
):
    project_id = user_api_key.project_id
    org_id = user_api_key.organization_id

    # Delete existing OpenAI credentials first to test POST
    client.delete(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )

    api_key = "sk-" + generate_random_string(10)
    # Now POST will create new credentials
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
    # Delete existing credentials first
    client.delete(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )

    # Even if mismatched IDs are sent, route uses API key context
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


def test_read_credentials_not_found(client: TestClient, user_api_key: APIKeyPublic):
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
    # Seed data already has OpenAI credentials - just test GET
    response = client.get(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200
    response_data = response.json()
    data = response_data.get("data", response_data)
    assert "api_key" in data
    # Seed data should have OpenAI credentials


def test_read_provider_credential_not_found(
    client: TestClient, user_api_key: APIKeyPublic
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
    assert "Credentials not found for provider" in response.json()["error"]


def test_update_credentials(
    client: TestClient,
    user_api_key: APIKeyPublic,
):
    # Update existing OpenAI credentials from seed data
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
    client: TestClient, user_api_key: APIKeyPublic
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
    client: TestClient, user_api_key: APIKeyPublic
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
    assert "Credentials not found for provider" in response.json()["error"]


def test_delete_all_credentials(
    client: TestClient,
    user_api_key: APIKeyPublic,
):
    # Delete existing credentials from seed data
    response = client.delete(
        f"{settings.API_V1_STR}/credentials/",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200  # Expect 200 for successful deletion
    response_data = response.json()
    # Check if response has 'data' key with message
    if "data" in response_data:
        assert (
            response_data["data"]["message"] == "All credentials deleted successfully"
        )

    # Verify the credentials are deleted
    response = client.get(
        f"{settings.API_V1_STR}/credentials/",
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response.status_code == 404  # Expect 404 as credentials are deleted
    assert "Credentials not found" in response.json()["error"]


def test_delete_all_credentials_not_found(
    client: TestClient, user_api_key: APIKeyPublic
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
    assert (
        "Credentials not found for this organization and project"
        in response.json()["error"]
    )


def test_duplicate_credential_creation(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    # Test verifies that the database unique constraint prevents duplicate credentials
    # for the same organization, project, and provider combination.
    # The constraint is defined in the model and migration f05d9c95100a.
    # Seed data ensures OpenAI credentials already exist for this user's project.

    # Use the existing helper function to get credential data
    credential = test_credential_data(db)

    # Try to create duplicate OpenAI credentials - should fail with 400
    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=credential.model_dump(),
        headers={"X-API-KEY": user_api_key.key},
    )

    # Should get 400 for duplicate credentials
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
    db: Session,
    user_api_key: APIKeyPublic,
):
    # Use existing credentials from seed data to verify encryption
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
    # Verify the stored credential is encrypted (not plaintext)
    assert isinstance(db_credential.credential, str)

    # Verify we can decrypt and get a valid structure
    decrypted_creds = decrypt_credentials(db_credential.credential)
    assert "api_key" in decrypted_creds
    assert decrypted_creds["api_key"].startswith("sk-")


def test_credential_encryption_consistency(
    client: TestClient, user_api_key: APIKeyPublic
):
    # Fetch existing seed data credentials
    response = client.get(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response.status_code == 200
    response_data = response.json()
    original_data = response_data.get("data", response_data)
    original_api_key = original_data["api_key"]

    # Verify decrypted value is returned
    assert original_api_key.startswith("sk-")

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

    # Verify updated credentials are decrypted correctly
    response = client.get(
        f"{settings.API_V1_STR}/credentials/provider/{Provider.OPENAI.value}",
        headers={"X-API-KEY": user_api_key.key},
    )
    assert response.status_code == 200
    response_data = response.json()
    data = response_data.get("data", response_data)
    assert data["api_key"] == new_api_key
