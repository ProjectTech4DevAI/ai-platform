import pytest
import random
import string
from fastapi.testclient import TestClient
from sqlmodel import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from app.models import (
    Credential,
    CredsCreate,
    Organization,
    OrganizationCreate,
    CredsUpdate,
)
from app.crud.credentials import (
    set_creds_for_org,
    get_creds_by_org,
    get_key_by_org,
    remove_creds_for_org,
    update_creds_for_org,
)
from app.main import app
from app.utils import APIResponse
from app.core.config import settings

client = TestClient(app)


# Helper function to generate random API key
def generate_random_string(length=10):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


@pytest.fixture
def test_credential(db: Session):
    # Create a unique organization name
    unique_org_name = "Test Organization " + generate_random_string(
        5
    )  # Ensure unique name

    # Check if the organization already exists by name
    existing_org = (
        db.query(Organization).filter(Organization.name == unique_org_name).first()
    )

    if existing_org:
        org = existing_org  # If organization exists, use the existing one
    else:
        # If not, create a new organization
        organization_data = OrganizationCreate(name=unique_org_name, is_active=True)
        org = Organization(**organization_data.dict())  # Create Organization instance
        db.add(org)  # Add to the session

        try:
            db.commit()  # Commit to save the organization to the database
            db.refresh(org)  # Refresh to get the organization_id
        except IntegrityError as e:
            db.rollback()  # Rollback the transaction in case of an error (e.g., duplicate key)
            raise ValueError(f"Error during organization commit: {str(e)}")

    # Generate a random API key for the test
    api_key = "sk-" + generate_random_string(10)

    # Create the credentials using the mock organization_id
    creds_data = CredsCreate(
        organization_id=org.id,  # Use the created organization_id
        is_active=True,
        credential={"openai": {"api_key": api_key}},
    )

    creds = set_creds_for_org(session=db, creds_add=creds_data)
    return creds


def test_create_credentials(db: Session, test_credential):
    creds = test_credential  # Using the fixture
    assert creds is not None
    assert creds.credential["openai"]["api_key"].startswith("sk-")
    assert creds.is_active is True
    assert creds.inserted_at is not None  # Ensure inserted_at is set


def test_get_creds_by_org(db: Session, test_credential):
    creds = test_credential  # Using the fixture
    retrieved_creds = get_creds_by_org(session=db, org_id=creds.organization_id)

    assert retrieved_creds is not None
    assert retrieved_creds.organization_id == creds.organization_id
    assert retrieved_creds.inserted_at is not None  # Ensure inserted_at is not None


def test_update_creds_for_org(db: Session, test_credential):
    creds = test_credential  # Using the fixture
    updated_creds_data = CredsUpdate(credential={"openai": {"api_key": "sk-newkey"}})

    updated_creds = update_creds_for_org(
        session=db, org_id=creds.organization_id, creds_in=updated_creds_data
    )

    assert updated_creds is not None
    assert updated_creds.credential["openai"]["api_key"] == "sk-newkey"
    assert updated_creds.updated_at is not None  # Ensure updated_at is set


def test_remove_creds_for_org(db: Session, test_credential):
    creds = test_credential  # Using the fixture
    removed_creds = remove_creds_for_org(session=db, org_id=creds.organization_id)

    assert removed_creds is not None
    assert removed_creds.organization_id == creds.organization_id

    # Ensure the deleted_at timestamp is set for soft delete
    assert removed_creds.deleted_at is not None  # Ensure deleted_at is set

    # Check that credentials are soft deleted and not removed
    deleted_creds = (
        db.query(Credential)
        .filter(Credential.organization_id == creds.organization_id)
        .first()
    )
    assert deleted_creds is not None  # Ensure the record still exists in the DB
    assert deleted_creds.deleted_at is not None  # Ensure it's marked as deleted


def test_remove_creds_for_org_not_found(db: Session):
    # Try to remove credentials for a non-existent organization ID (999)
    non_existing_org_id = 999

    removed_creds = remove_creds_for_org(session=db, org_id=non_existing_org_id)

    # Assert that no credentials were removed since they don't exist
    assert removed_creds is None
