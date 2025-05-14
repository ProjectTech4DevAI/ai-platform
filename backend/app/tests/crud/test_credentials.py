import uuid
from sqlmodel import Session
import pytest
from datetime import datetime

from app.crud import credentials as credentials_crud
from app.models import Credential, CredsCreate, CredsUpdate, Organization, Project
from app.tests.utils.utils import random_email
from app.core.security import get_password_hash


def create_organization_and_project(db: Session) -> tuple[Organization, Project]:
    """Helper function to create an organization and a project."""
    organization = Organization(
        name=f"Test Organization {uuid.uuid4()}", is_active=True
    )
    db.add(organization)
    db.commit()
    db.refresh(organization)

    project = Project(
        name=f"Test Project {uuid.uuid4()}",
        description="A test project",
        organization_id=organization.id,
        is_active=True,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    return organization, project


def test_set_creds_for_org(db: Session) -> None:
    """Test setting credentials for an organization."""
    organization, _ = create_organization_and_project(db)

    # Test credentials for supported providers
    creds_data = {
        "openai": {"api_key": "test-openai-key"},
        "langfuse": {
            "public_key": "test-public-key",
            "secret_key": "test-secret-key",
            "host": "https://cloud.langfuse.com",
        },
    }

    creds_create = CredsCreate(organization_id=organization.id, credential=creds_data)

    created_creds = credentials_crud.set_creds_for_org(
        session=db, creds_add=creds_create
    )

    assert len(created_creds) == 2
    assert all(cred.organization_id == organization.id for cred in created_creds)
    assert all(cred.is_active for cred in created_creds)
    assert {cred.provider for cred in created_creds} == {"openai", "langfuse"}


def test_set_creds_for_org_with_project(db: Session) -> None:
    """Test setting credentials for an organization with a specific project."""
    organization, project = create_organization_and_project(db)

    creds_data = {"openai": {"api_key": "test-openai-key"}}

    creds_create = CredsCreate(
        organization_id=organization.id, project_id=project.id, credential=creds_data
    )

    created_creds = credentials_crud.set_creds_for_org(
        session=db, creds_add=creds_create
    )

    assert len(created_creds) == 1
    assert created_creds[0].organization_id == organization.id
    assert created_creds[0].project_id == project.id
    assert created_creds[0].provider == "openai"
    assert created_creds[0].is_active


def test_get_creds_by_org(db: Session) -> None:
    """Test retrieving all credentials for an organization."""
    organization, _ = create_organization_and_project(db)

    # Set up test credentials
    creds_data = {
        "openai": {"api_key": "test-openai-key"},
        "langfuse": {
            "public_key": "test-public-key",
            "secret_key": "test-secret-key",
            "host": "https://cloud.langfuse.com",
        },
    }

    creds_create = CredsCreate(organization_id=organization.id, credential=creds_data)
    credentials_crud.set_creds_for_org(session=db, creds_add=creds_create)

    # Test retrieving credentials
    retrieved_creds = credentials_crud.get_creds_by_org(
        session=db, org_id=organization.id
    )

    assert len(retrieved_creds) == 2
    assert all(cred.organization_id == organization.id for cred in retrieved_creds)
    assert {cred.provider for cred in retrieved_creds} == {"openai", "langfuse"}


def test_get_provider_credential(db: Session) -> None:
    """Test retrieving credentials for a specific provider."""
    organization, _ = create_organization_and_project(db)

    # Set up test credentials
    creds_data = {"openai": {"api_key": "test-openai-key"}}

    creds_create = CredsCreate(organization_id=organization.id, credential=creds_data)
    credentials_crud.set_creds_for_org(session=db, creds_add=creds_create)

    # Test retrieving specific provider credentials
    retrieved_cred = credentials_crud.get_provider_credential(
        session=db, org_id=organization.id, provider="openai"
    )

    assert retrieved_cred is not None
    assert "api_key" in retrieved_cred
    assert retrieved_cred["api_key"] == "test-openai-key"


def test_update_creds_for_org(db: Session) -> None:
    """Test updating credentials for a provider."""
    organization, _ = create_organization_and_project(db)

    # Set up initial credentials
    initial_creds = {"openai": {"api_key": "initial-key"}}
    creds_create = CredsCreate(
        organization_id=organization.id, credential=initial_creds
    )
    credentials_crud.set_creds_for_org(session=db, creds_add=creds_create)

    # Update credentials
    updated_creds = {"api_key": "updated-key"}
    creds_update = CredsUpdate(provider="openai", credential=updated_creds)

    updated = credentials_crud.update_creds_for_org(
        session=db, org_id=organization.id, creds_in=creds_update
    )

    assert len(updated) == 1
    assert updated[0].provider == "openai"
    retrieved_cred = credentials_crud.get_provider_credential(
        session=db, org_id=organization.id, provider="openai"
    )
    assert retrieved_cred["api_key"] == "updated-key"


def test_remove_provider_credential(db: Session) -> None:
    """Test removing credentials for a specific provider."""
    organization, _ = create_organization_and_project(db)

    # Set up test credentials
    creds_data = {
        "openai": {"api_key": "test-openai-key"},
        "langfuse": {
            "public_key": "test-public-key",
            "secret_key": "test-secret-key",
            "host": "https://cloud.langfuse.com",
        },
    }

    creds_create = CredsCreate(organization_id=organization.id, credential=creds_data)
    credentials_crud.set_creds_for_org(session=db, creds_add=creds_create)

    # Remove one provider's credentials
    removed = credentials_crud.remove_provider_credential(
        session=db, org_id=organization.id, provider="openai"
    )

    assert removed.is_active is False
    assert removed.updated_at is not None

    # Verify the credentials are no longer retrievable
    retrieved_cred = credentials_crud.get_provider_credential(
        session=db, org_id=organization.id, provider="openai"
    )
    assert retrieved_cred is None


def test_remove_creds_for_org(db: Session) -> None:
    """Test removing all credentials for an organization."""
    organization, _ = create_organization_and_project(db)

    # Set up test credentials
    creds_data = {
        "openai": {"api_key": "test-openai-key"},
        "langfuse": {
            "public_key": "test-public-key",
            "secret_key": "test-secret-key",
            "host": "https://cloud.langfuse.com",
        },
    }

    creds_create = CredsCreate(organization_id=organization.id, credential=creds_data)
    credentials_crud.set_creds_for_org(session=db, creds_add=creds_create)

    # Remove all credentials
    removed = credentials_crud.remove_creds_for_org(session=db, org_id=organization.id)

    assert len(removed) == 2
    assert all(not cred.is_active for cred in removed)
    assert all(cred.updated_at is not None for cred in removed)

    # Verify no credentials are retrievable
    retrieved_creds = credentials_crud.get_creds_by_org(
        session=db, org_id=organization.id
    )
    assert len(retrieved_creds) == 0


def test_invalid_provider(db: Session) -> None:
    """Test handling of invalid provider names."""
    organization, _ = create_organization_and_project(db)

    # Test with unsupported provider
    creds_data = {"gemini": {"api_key": "test-key"}}

    creds_create = CredsCreate(organization_id=organization.id, credential=creds_data)

    with pytest.raises(ValueError, match="Unsupported provider"):
        credentials_crud.set_creds_for_org(session=db, creds_add=creds_create)


def test_duplicate_provider_credentials(db: Session) -> None:
    """Test handling of duplicate provider credentials."""
    organization, _ = create_organization_and_project(db)

    # Set up initial credentials
    creds_data = {"openai": {"api_key": "test-key"}}

    creds_create = CredsCreate(organization_id=organization.id, credential=creds_data)
    credentials_crud.set_creds_for_org(session=db, creds_add=creds_create)

    # Verify credentials exist and are active
    existing_creds = credentials_crud.get_provider_credential(
        session=db, org_id=organization.id, provider="openai"
    )
    assert existing_creds is not None
    assert "api_key" in existing_creds
    assert existing_creds["api_key"] == "test-key"


def test_langfuse_credential_validation(db: Session) -> None:
    """Test validation of Langfuse credentials structure."""
    organization, _ = create_organization_and_project(db)

    # Test with missing required fields
    invalid_creds = {
        "langfuse": {
            "public_key": "test-public-key",
            "secret_key": "test-secret-key"
            # Missing host
        }
    }

    creds_create = CredsCreate(
        organization_id=organization.id, credential=invalid_creds
    )

    with pytest.raises(ValueError):
        credentials_crud.set_creds_for_org(session=db, creds_add=creds_create)

    # Test with valid Langfuse credentials
    valid_creds = {
        "langfuse": {
            "public_key": "test-public-key",
            "secret_key": "test-secret-key",
            "host": "https://cloud.langfuse.com",
        }
    }

    creds_create = CredsCreate(organization_id=organization.id, credential=valid_creds)

    created_creds = credentials_crud.set_creds_for_org(
        session=db, creds_add=creds_create
    )
    assert len(created_creds) == 1
    assert created_creds[0].provider == "langfuse"
