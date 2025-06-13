import uuid
from datetime import datetime
from sqlmodel import Session
from app.crud import api_key as api_key_crud
from app.models import APIKey, User, Organization
from app.tests.utils.utils import random_email
from app.core.security import get_password_hash, verify_password, decrypt_api_key
from app.core.exception_handlers import HTTPException


# Helper function to create a user
def create_test_user(db: Session) -> User:
    user = User(email=random_email(), hashed_password=get_password_hash("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# Helper function to create an organization with a random name
def create_test_organization(db: Session) -> Organization:
    org = Organization(
        name=f"Test Organization {uuid.uuid4()}", description="Test Organization"
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def test_create_api_key(db: Session) -> None:
    user = create_test_user(db)
    org = create_test_organization(db)

    api_key = api_key_crud.create_api_key(db, org.id, user.id)

    assert api_key.key.startswith("ApiKey ")
    assert len(api_key.key) > 32
    assert api_key.organization_id == org.id
    assert api_key.user_id == user.id


def test_get_api_key(db: Session) -> None:
    user = create_test_user(db)
    org = create_test_organization(db)

    created_key = api_key_crud.create_api_key(db, org.id, user.id)
    retrieved_key = api_key_crud.get_api_key(db, created_key.id)

    assert retrieved_key is not None
    assert retrieved_key.id == created_key.id
    # The key should be in its original format
    assert retrieved_key.key.startswith("ApiKey ")
    assert len(retrieved_key.key) > 32


def test_get_api_key_not_found(db: Session) -> None:
    result = api_key_crud.get_api_key(db, 9999)  # Non-existent ID
    assert result is None


def test_get_api_keys_by_organization(db: Session) -> None:
    user1 = create_test_user(db)
    user2 = create_test_user(db)
    org = create_test_organization(db)

    api_key1 = api_key_crud.create_api_key(db, org.id, user1.id)
    api_key2 = api_key_crud.create_api_key(db, org.id, user2.id)

    api_keys = api_key_crud.get_api_keys_by_organization(db, org.id)

    assert len(api_keys) == 2
    # Verify that the keys are in their original format
    for key in api_keys:
        assert key.key.startswith("ApiKey ")
        assert len(key.key) > 32  # Raw key should be longer than 32 characters
        assert key.organization_id == org.id
        assert key.user_id in [user1.id, user2.id]


def test_get_api_key_by_value(db: Session) -> None:
    user = create_test_user(db)
    org = create_test_organization(db)

    # Create an API key
    api_key = api_key_crud.create_api_key(db, org.id, user.id)
    # Get the raw key that was returned during creation
    raw_key = api_key.key

    # Test retrieving the API key by its value
    retrieved_key = api_key_crud.get_api_key_by_value(db, raw_key)

    assert retrieved_key is not None
    assert retrieved_key.id == api_key.id
    assert retrieved_key.organization_id == org.id
    assert retrieved_key.user_id == user.id
    # The key should be in its original format
    assert retrieved_key.key == raw_key  # Should be exactly the same key
    assert retrieved_key.key.startswith("ApiKey ")
    assert len(retrieved_key.key) > 32


def test_get_api_key_by_user_org(db: Session) -> None:
    user = create_test_user(db)
    org = create_test_organization(db)

    api_key = api_key_crud.create_api_key(db, org.id, user.id)
    retrieved_key = api_key_crud.get_api_key_by_user_org(db, org.id, user.id)

    assert retrieved_key is not None
    assert retrieved_key.id == api_key.id
    assert retrieved_key.organization_id == org.id
    assert retrieved_key.user_id == user.id
    # The key should be in its original format
    assert retrieved_key.key.startswith("ApiKey ")
    assert len(retrieved_key.key) > 32


def test_get_api_key_by_user_org_not_found(db: Session) -> None:
    org = create_test_organization(db)
    user_id = uuid.uuid4()
    result = api_key_crud.get_api_key_by_user_org(db, org.id, user_id)
    assert result is None
