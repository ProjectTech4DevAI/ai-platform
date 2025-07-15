import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import app
from app.crud import get_provider_credential
from app.models import Organization, Project
from app.core.config import settings
from app.core.providers import Provider
from app.models.credentials import Credential
from app.core.security import decrypt_credentials
from app.tests.utils.utils import (
    generate_random_string,
    get_non_existent_id,
)
from app.tests.utils.test_data import (
    create_test_credential,
    create_test_organization,
    create_test_project,
    test_credential_data,
)


client = TestClient(app)

def create_test_credentials(db: Session):
    return create_test_credential(db)


def test_set_credential(db: Session, superuser_token_headers: dict[str, str]):
    project = create_test_project(db)

    api_key = "sk-" + generate_random_string(10)
    credential_data = {
        "organization_id": project.organization_id,
        "project_id": project.id,
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
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 1

    assert data[0]["organization_id"] == project.organization_id
    assert data[0]["provider"] == Provider.OPENAI.value
    assert data[0]["credential"]["model"] == "gpt-4"


def test_set_credentials_for_invalid_project_org_relationship(
    db: Session, superuser_token_headers: dict[str, str]
):
    org1 = create_test_organization(db)
    project2 = create_test_project(db)

    credential_data_invalid = {
        "organization_id": org1.id,
        "is_active": True,
        "project_id": project2.id,
        "credential": {Provider.OPENAI.value: {"api_key": "sk-123", "model": "gpt-4"}},
    }

    response_invalid = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=credential_data_invalid,
        headers=superuser_token_headers,
    )
    assert response_invalid.status_code == 400
    assert (
        response_invalid.json()["error"]
        == "Project does not belong to the specified organization"
    )

def test_set_credentials_for_project_not_found(
    db: Session, superuser_token_headers: dict[str, str]
):
    # Setup: Create an organization but no project
    org = create_test_organization(db)
    non_existent_project_id = get_non_existent_id(db, Project)

    credential_data_invalid_project = {
        "organization_id": org.id,
        "is_active": True,
        "project_id": non_existent_project_id,
        "credential": {Provider.OPENAI.value: {"api_key": "sk-123", "model": "gpt-4"}},
    }

    response_invalid_project = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=credential_data_invalid_project,
        headers=superuser_token_headers,
    )

    assert response_invalid_project.status_code == 404
    assert response_invalid_project.json()["error"] == "Project not found"


def test_read_credentials_with_creds(
    db: Session, superuser_token_headers: dict[str, str], create_test_credentials
):
    _, project = create_test_credentials

    credential = get_provider_credential(
        session=db,
        org_id=project.organization_id,
        provider="openai",
        project_id=project.id,
        full=True,
    )

    response = client.get(
        f"{settings.API_V1_STR}/credentials/{credential.organization_id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["organization_id"] == project.organization_id
    assert data[0]["provider"] == Provider.OPENAI.value
    assert data[0]["credential"]["model"] == "gpt-4"


def test_read_credentials_not_found(
    db: Session, superuser_token_headers: dict[str, str]
):
    non_existent_creds_id = get_non_existent_id(db, Credential)
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{non_existent_creds_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert "Credentials not found" in response.json()["error"]


def test_read_provider_credential(
    db: Session, superuser_token_headers: dict[str, str], create_test_credentials
):
    _, project = create_test_credentials

    response = client.get(
        f"{settings.API_V1_STR}/credentials/{project.organization_id}/{Provider.OPENAI.value}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model"] == "gpt-4"
    assert "api_key" in data


def test_read_provider_credential_not_found(
    db: Session, superuser_token_headers: dict[str, str]
):
    org = create_test_organization(db)

    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}/{Provider.OPENAI.value}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"] == "Provider credentials not found"


def test_update_credentials(
    db: Session, superuser_token_headers: dict[str, str], create_test_credentials
):
    _, project = create_test_credentials

    credential = get_provider_credential(
        session=db,
        org_id=project.organization_id,
        provider="openai",
        project_id=project.id,
        full=True,
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
        f"{settings.API_V1_STR}/credentials/{credential.organization_id}",
        json=update_data,
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["provider"] == Provider.OPENAI.value
    assert data[0]["credential"]["model"] == "gpt-4-turbo"
    assert data[0]["updated_at"] is not None


def test_update_credentials_failed_update(
    db: Session, superuser_token_headers: dict[str, str], create_test_credentials
):
    _, project = create_test_credentials

    credential = get_provider_credential(
        session=db,
        org_id=project.organization_id,
        provider="openai",
        project_id=project.id,
        full=True,
    )

    org_without_credential = create_test_organization(db)

    existing_credential = (
        db.query(Credential)
        .filter(credential.organization_id == org_without_credential.id)
        .all()
    )
    assert len(existing_credential) == 0

    update_data = {
        "provider": Provider.OPENAI.value,
        "credential": {
            "api_key": "sk-" + generate_random_string(),
            "model": "gpt-4-turbo",
            "temperature": 0.8,
        },
    }

    response_invalid_org = client.patch(
        f"{settings.API_V1_STR}/credentials/{org_without_credential.id}",
        json=update_data,
        headers=superuser_token_headers,
    )
    assert response_invalid_org.status_code == 404
    assert (
        response_invalid_org.json()["error"]
        == "Credentials not found for this provider"
    )


def test_update_credentials_not_found(
    db: Session, superuser_token_headers: dict[str, str]
):
    non_existent_org_id = get_non_existent_id(db, Organization)

    update_data = {
        "provider": Provider.OPENAI.value,
        "credential": {
            "api_key": "sk-" + generate_random_string(),
            "model": "gpt-4",
            "temperature": 0.7,
        },
    }

    response = client.patch(
        f"{settings.API_V1_STR}/credentials/{non_existent_org_id}",
        json=update_data,
        headers=superuser_token_headers,
    )

    assert response.status_code == 404  # Expect 404 for non-existent organization
    assert "Organization not found" in response.json()["error"]


def test_delete_provider_credential(
    db: Session, superuser_token_headers: dict[str, str], create_test_credentials
):
    _, project = create_test_credentials

    credential = get_provider_credential(
        session=db,
        org_id=project.organization_id,
        provider="openai",
        project_id=project.id,
        full=True,
    )

    response = client.delete(
        f"{settings.API_V1_STR}/credentials/{credential.organization_id}/{Provider.OPENAI.value}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["message"] == "Provider credentials removed successfully"


def test_delete_provider_credential_not_found(
    db: Session, superuser_token_headers: dict[str, str]
):
    org = create_test_organization(db)

    response = client.delete(
        f"{settings.API_V1_STR}/credentials/{org.id}/{Provider.OPENAI.value}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"] == "Provider credentials not found"


def test_delete_all_credentials(
    db: Session, superuser_token_headers: dict[str, str], create_test_credentials
):
    _, project = create_test_credentials

    credential = get_provider_credential(
        session=db,
        org_id=project.organization_id,
        provider="openai",
        project_id=project.id,
        full=True,
    )
    response = client.delete(
        f"{settings.API_V1_STR}/credentials/{credential.organization_id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200  # Expect 200 for successful deletion
    data = response.json()["data"]
    assert data["message"] == "Credentials deleted successfully"

    # Verify the credentials are soft deleted
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{credential.organization_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404  # Expect 404 as credentials are soft deleted
    assert response.json()["error"] == "Credentials not found"


def test_delete_all_credentials_not_found(
    db: Session, superuser_token_headers: dict[str, str]
):
    non_existent_credential_id = get_non_existent_id(db, Credential)
    response = client.delete(
        f"{settings.API_V1_STR}/credentials/{non_existent_credential_id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
    assert "Credentials for organization not found" in response.json()["error"]


def test_duplicate_credential_creation(
    db: Session, superuser_token_headers: dict[str, str]
):
    credential = test_credential_data(db)

    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=credential.dict(),
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    # Try to create the same credentials again
    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=credential.dict(),
        headers=superuser_token_headers,
    )
    assert response.status_code == 400

    assert "already exist" in response.json()["error"]


def test_multiple_provider_credentials(
    db: Session, superuser_token_headers: dict[str, str]
):
    org = create_test_organization(db)

    # Create OpenAI credentials
    openai_credential = {
        "organization_id": org.id,
        "project_id": project.id,
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
        "organization_id": org.id,
        "project_id": project.id,
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
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=langfuse_credential,
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    # Fetch all credentials
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2
    providers = [cred["provider"] for cred in data]
    assert Provider.OPENAI.value in providers
    assert Provider.LANGFUSE.value in providers


def test_credential_encryption(db: Session, superuser_token_headers: dict[str, str]):
    credential = test_credential_data(db)
    original_api_key = credential.credential[Provider.OPENAI.value]["api_key"]

    # Create credentials
    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=credential.dict(),
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    db_credential = (
        db.query(Credential)
        .filter(
            Credential.organization_id == credential.organization_id,
            Credential.provider == Provider.OPENAI.value,
        )
        .first()
    )

    assert db_credential is not None
    # Verify the stored credential is encrypted
    assert db_credential.credential != original_api_key

    # Verify we can decrypt and get the original value
    decrypted_creds = decrypt_credentials(db_credential.credential)
    assert decrypted_creds["api_key"] == original_api_key


def test_credential_encryption_consistency(
    db: Session, superuser_token_headers: dict[str, str]
):
    credentials = test_credential_data(db)
    original_api_key = credentials.credential[Provider.OPENAI.value]["api_key"]

    # Create credentials
    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=credentials.dict(),
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    # Fetch the credentials through the API
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{credentials.organization_id}/{Provider.OPENAI.value}",
        headers=superuser_token_headers,
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
        f"{settings.API_V1_STR}/credentials/{credentials.organization_id}",
        json=update_data,
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    response = client.get(
        f"{settings.API_V1_STR}/credentials/{credentials.organization_id}/{Provider.OPENAI.value}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["api_key"] == new_api_key
