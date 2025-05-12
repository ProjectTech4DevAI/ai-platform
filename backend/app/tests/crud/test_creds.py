import pytest
import random
import string
from fastapi.testclient import TestClient
from sqlmodel import Session
from sqlalchemy.exc import IntegrityError

from app.models import (
    Credential,
    CredsCreate,
    CredsUpdate,
    Organization,
    OrganizationCreate,
)
from app.crud.credentials import (
    set_creds_for_org,
    get_creds_by_org,
    get_key_by_org,
    update_creds_for_org,
    remove_creds_for_org,
)
from app.core.providers import Provider
from app.core.security import encrypt_credentials, decrypt_credentials
from app.main import app

client = TestClient(app)


def generate_random_string(length=10):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


@pytest.fixture
def org_with_creds(db: Session):
    # Create test organization
    org = Organization(name="Test Org")
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create test credentials
    test_creds = CredsCreate(
        organization_id=org.id,
        credential={
            Provider.OPENAI.value: {
                "api_key": "sk-" + generate_random_string(12),
                "model": "gpt-4",
                "temperature": 0.7,
            }
        },
    )
    creds = set_creds_for_org(session=db, creds_add=test_creds)
    return org, creds


def test_create_credentials(db: Session, org_with_creds):
    org, creds = org_with_creds
    assert creds is not None
    assert len(creds) == 1
    assert creds[0].provider == Provider.OPENAI.value

    # Decrypt the stored credentials
    decrypted_creds = decrypt_credentials(creds[0].credential)
    assert "api_key" in decrypted_creds
    assert decrypted_creds["api_key"].startswith("sk-")
    assert decrypted_creds["model"] == "gpt-4"
    assert decrypted_creds["temperature"] == 0.7
    assert creds[0].is_active
    assert creds[0].inserted_at is not None


def test_get_creds_by_org(db: Session, org_with_creds):
    org, creds = org_with_creds
    retrieved = get_creds_by_org(session=db, org_id=org.id)
    assert retrieved is not None
    assert len(retrieved) == 1
    assert retrieved[0].organization_id == org.id
    assert retrieved[0].provider == Provider.OPENAI.value
    assert "api_key" in retrieved[0].credential
    assert retrieved[0].inserted_at is not None


def test_update_creds_for_org(db: Session, org_with_creds):
    org, _ = org_with_creds
    new_api_key = "sk-" + generate_random_string(12)
    update_data = CredsUpdate(
        provider=Provider.OPENAI.value,
        credential={"api_key": new_api_key, "model": "gpt-4-turbo", "temperature": 0.8},
    )

    updated = update_creds_for_org(session=db, org_id=org.id, creds_in=update_data)

    assert updated is not None
    assert len(updated) == 1
    # Decrypt the stored credentials before asserting
    decrypted_creds = decrypt_credentials(updated[0].credential)
    assert decrypted_creds["api_key"] == new_api_key
    assert decrypted_creds["model"] == "gpt-4-turbo"
    assert decrypted_creds["temperature"] == 0.8
    assert updated[0].updated_at is not None


def test_remove_creds_for_org(db: Session, org_with_creds):
    org, creds = org_with_creds
    removed = remove_creds_for_org(session=db, org_id=org.id)

    assert removed is not None
    assert len(removed) == 1
    assert removed[0].organization_id == org.id
    assert removed[0].deleted_at is not None

    # Ensure the record is still present but soft-deleted
    still_exists = (
        db.query(Credential).filter(Credential.organization_id == org.id).first()
    )
    assert still_exists is not None
    assert still_exists.deleted_at is not None


def test_remove_creds_for_org_not_found(db: Session):
    removed = remove_creds_for_org(session=db, org_id=999999)
    assert removed is None
