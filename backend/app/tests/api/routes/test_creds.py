import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
import random
import string

from app.main import app
from app.api.deps import get_db
from app.crud.credentials import set_creds_for_org
from app.models import CredsCreate, Organization, OrganizationCreate, Project
from app.core.config import settings
from app.core.security import encrypt_api_key
from app.core.providers import Provider
from app.models.credentials import Credential
from app.core.security import decrypt_credentials


client = TestClient(app)


def generate_random_string(length=10):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


@pytest.fixture
def create_organization_and_creds(db: Session):
    unique_org_name = "Test Organization " + generate_random_string(5)
    org = Organization(name=unique_org_name, is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)

    api_key = "sk-" + generate_random_string(10)
    creds_data = CredsCreate(
        organization_id=org.id,
        is_active=True,
        credential={
            Provider.OPENAI.value: {
                "api_key": api_key,
                "model": "gpt-4",
                "temperature": 0.7,
            }
        },
    )
    return org, creds_data


def test_set_creds_for_org(db: Session, superuser_token_headers: dict[str, str]):
    org = Organization(name="Org for Set Creds", is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)

    api_key = "sk-" + generate_random_string(10)
    creds_data = {
        "organization_id": org.id,
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
        json=creds_data,
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["organization_id"] == org.id
    assert data[0]["provider"] == Provider.OPENAI.value
    assert data[0]["credential"]["model"] == "gpt-4"


def test_set_creds_for_invalid_project_org_relationship(
    db: Session, superuser_token_headers: dict[str, str]
):
    # Setup: Create two organizations and one project for each
    org1 = Organization(name="Org 1", is_active=True)
    org2 = Organization(name="Org 2", is_active=True)
    db.add_all([org1, org2])
    db.commit()
    db.refresh(org1)
    db.refresh(org2)

    project2 = Project(name="Project Org2", organization_id=org2.id)
    db.add(project2)
    db.commit()

    # Invalid case: Organization mismatch (org1's creds for project2 of org2)
    creds_data_invalid = {
        "organization_id": org1.id,
        "is_active": True,
        "project_id": project2.id,  # Invalid project for org1
        "credential": {Provider.OPENAI.value: {"api_key": "sk-123", "model": "gpt-4"}},
    }

    response_invalid = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=creds_data_invalid,
        headers=superuser_token_headers,
    )
    assert response_invalid.status_code == 400
    print(response_invalid.json())
    assert (
        response_invalid.json()["error"]
        == "Project does not belong to the specified organization"
    )


def test_set_creds_for_project_not_found(
    db: Session, superuser_token_headers: dict[str, str]
):
    # Setup: Create an organization but no project
    org = Organization(name="Org for Project Not Found", is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)

    creds_data_invalid_project = {
        "organization_id": org.id,
        "is_active": True,
        "project_id": 99999,
        "credential": {Provider.OPENAI.value: {"api_key": "sk-123", "model": "gpt-4"}},
    }

    response_invalid_project = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=creds_data_invalid_project,
        headers=superuser_token_headers,
    )

    assert response_invalid_project.status_code == 404
    assert response_invalid_project.json()["error"] == "Project not found"


def test_read_credentials_with_creds(
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["organization_id"] == org.id
    assert data[0]["provider"] == Provider.OPENAI.value
    assert data[0]["credential"]["model"] == "gpt-4"


def test_read_credentials_not_found(
    db: Session, superuser_token_headers: dict[str, str]
):
    response = client.get(
        f"{settings.API_V1_STR}/credentials/999999",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert "Credentials not found" in response.json()["error"]


def test_read_provider_credential(
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}/{Provider.OPENAI.value}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model"] == "gpt-4"
    assert "api_key" in data


def test_read_provider_credential_not_found(
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, _ = create_organization_and_creds

    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}/{Provider.OPENAI.value}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"] == "Provider credentials not found"


def test_update_credentials(
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    update_data = {
        "provider": Provider.OPENAI.value,
        "credential": {
            "api_key": "sk-" + generate_random_string(),
            "model": "gpt-4-turbo",
            "temperature": 0.8,
        },
    }

    response = client.patch(
        f"{settings.API_V1_STR}/credentials/{org.id}",
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
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, creds_data = create_organization_and_creds

    set_creds_for_org(session=db, creds_add=creds_data)

    org_without_creds = Organization(name="Org Without Creds", is_active=True)
    db.add(org_without_creds)
    db.commit()
    db.refresh(org_without_creds)

    existing_creds = (
        db.query(Credential)
        .filter(Credential.organization_id == org_without_creds.id)
        .all()
    )
    assert len(existing_creds) == 0

    update_data = {
        "provider": Provider.OPENAI.value,
        "credential": {
            "api_key": "sk-" + generate_random_string(),
            "model": "gpt-4-turbo",
            "temperature": 0.8,
        },
    }

    response_invalid_org = client.patch(
        f"{settings.API_V1_STR}/credentials/{org_without_creds.id}",  # Valid org id but no creds
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
    # Create a non-existent organization ID
    non_existent_org_id = 999999

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
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    response = client.delete(
        f"{settings.API_V1_STR}/credentials/{org.id}/{Provider.OPENAI.value}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["message"] == "Provider credentials removed successfully"


def test_delete_provider_credential_not_found(
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, _ = create_organization_and_creds

    response = client.delete(
        f"{settings.API_V1_STR}/credentials/{org.id}/{Provider.OPENAI.value}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
    print(response.json())
    assert response.json()["error"] == f"Provider credentials not found"


def test_delete_all_credentials(
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    response = client.delete(
        f"{settings.API_V1_STR}/credentials/{org.id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200  # Expect 200 for successful deletion
    data = response.json()["data"]
    assert data["message"] == "Credentials deleted successfully"

    # Verify the credentials are soft deleted
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404  # Expect 404 as credentials are soft deleted
    assert response.json()["error"] == "Credentials not found"


def test_delete_all_credentials_not_found(
    db: Session, superuser_token_headers: dict[str, str]
):
    response = client.delete(
        f"{settings.API_V1_STR}/credentials/999999",
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
    assert "Credentials for organization not found" in response.json()["error"]


def test_duplicate_credential_creation(
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    # First create credentials
    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=creds_data.dict(),
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    # Try to create the same credentials again
    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=creds_data.dict(),
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert "already exist" in response.json()["error"]


def test_multiple_provider_credentials(
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, _ = create_organization_and_creds

    # Create OpenAI credentials
    openai_creds = {
        "organization_id": org.id,
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
    langfuse_creds = {
        "organization_id": org.id,
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
        json=openai_creds,
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=langfuse_creds,
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


def test_credential_encryption(
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    original_api_key = creds_data.credential[Provider.OPENAI.value]["api_key"]

    # Create credentials
    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=creds_data.dict(),
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    db_cred = (
        db.query(Credential)
        .filter(
            Credential.organization_id == org.id,
            Credential.provider == Provider.OPENAI.value,
        )
        .first()
    )

    assert db_cred is not None
    # Verify the stored credential is encrypted
    assert db_cred.credential != original_api_key

    # Verify we can decrypt and get the original value
    decrypted_creds = decrypt_credentials(db_cred.credential)
    assert decrypted_creds["api_key"] == original_api_key


def test_credential_encryption_consistency(
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    original_api_key = creds_data.credential[Provider.OPENAI.value]["api_key"]

    # Create credentials
    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=creds_data.dict(),
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    # Fetch the credentials through the API
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}/{Provider.OPENAI.value}",
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
        f"{settings.API_V1_STR}/credentials/{org.id}",
        json=update_data,
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    # Verify the updated value is also properly encrypted/decrypted
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}/{Provider.OPENAI.value}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["api_key"] == new_api_key
