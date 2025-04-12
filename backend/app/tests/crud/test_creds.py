import pytest
import random
import string

from fastapi.testclient import TestClient
from sqlmodel import Session
from sqlalchemy.exc import IntegrityError

from app.models import Credential, CredsCreate, Organization, OrganizationCreate
from app.crud.credentials import (
    set_creds_for_org,
    get_creds_by_org,
    get_key_by_org,
    remove_creds_for_org,
)
from app.main import app
from app.utils import APIResponse
from app.core.config import settings

client = TestClient(app)


# Helper function to generate random API key
def generate_random_string(length=10):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


# Fixture for setting up a test organization with credentials
@pytest.fixture
def test_credential(db: Session):
    # Generate a unique organization name
    unique_org_name = "Test Organization " + generate_random_string(
        5
    )  # Ensure unique name

    # Check if the organization already exists in the database
    existing_org = (
        db.query(Organization).filter(Organization.name == unique_org_name).first()
    )

    if existing_org:
        # If the organization already exists, use the existing one
        org = existing_org
    else:
        # If the organization does not exist, create a new one
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

    # Return the credentials and the organization
    return creds


def test_set_creds_for_org(db: Session):
    unique_org_id = 1  # Use an existing organization ID or create a new one
    api_key = "sk-" + generate_random_string(10)

    org = Organization(id=unique_org_id, name="Test Organization", is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)  # Ensure the organization is persisted and we get the org_id

    creds_data = CredsCreate(
        organization_id=unique_org_id,
        is_active=True,
        credential={"openai": {"api_key": api_key}},
    )

    creds = set_creds_for_org(session=db, creds_add=creds_data)

    assert creds is not None
    assert creds.organization_id == unique_org_id
    assert creds.credential["openai"]["api_key"] == api_key
    assert creds.is_active is True

    stored_creds = (
        db.query(Credential).filter(Credential.organization_id == unique_org_id).first()
    )
    assert stored_creds is not None
    assert stored_creds.organization_id == unique_org_id
    assert stored_creds.credential["openai"]["api_key"] == api_key
    assert stored_creds.is_active is True


# Test for getting credentials using `get_creds_by_org`
def test_get_creds_by_org(db: Session, test_credential: Credential):
    creds = get_creds_by_org(session=db, org_id=test_credential.organization_id)
    assert creds is not None
    assert creds.organization_id == test_credential.organization_id
    assert "openai" in creds.credential
    assert "api_key" in creds.credential["openai"]


# Test for retrieving API key using `get_key_by_org`
def test_get_key_by_org(db: Session, test_credential: Credential):
    api_key = get_key_by_org(session=db, org_id=test_credential.organization_id)
    assert api_key == test_credential.credential["openai"]["api_key"]


def test_get_key_by_org_not_found(db: Session):
    # Test for an organization that does not exist in the database
    api_key = get_key_by_org(session=db, org_id=999)
    assert api_key is None  # No API key should be found for a non-existent org


# Test for removing credentials using `remove_creds_for_org`
def test_remove_creds_for_org(db: Session, test_credential: Credential):
    creds = remove_creds_for_org(session=db, org_id=test_credential.organization_id)
    assert creds is not None  # Ensure the credentials were found and deleted
    assert creds.organization_id == test_credential.organization_id


def test_remove_creds_for_org_not_found(db: Session):
    # Test trying to remove credentials for an organization that doesn't exist
    creds = remove_creds_for_org(session=db, org_id=999)
    assert (
        creds is None
    )  # No credentials should be found or removed for a non-existent org
