import uuid
import pytest
from sqlmodel import Session, select
from app.crud import api_key as api_key_crud
from app.models import APIKey, User, Organization, Project
from app.tests.utils.utils import random_email
from app.core.security import get_password_hash, verify_password, decrypt_api_key


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


def create_test_project(db: Session, organization_id: int) -> Project:
    project = Project(
        name=f"Test Project {uuid.uuid4()}",
        description="Test project",
        organization_id=organization_id,
        is_active=True,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def test_create_api_key(db: Session) -> None:
    user = create_test_user(db)
    org = create_test_organization(db)
    project = create_test_project(db, org.id)

    api_key = api_key_crud.create_api_key(db, org.id, user.id, project.id)

    assert api_key.key.startswith("ApiKey ")
    assert len(api_key.key) > 32
    assert api_key.organization_id == org.id
    assert api_key.user_id == user.id
    assert api_key.project_id == project.id


def test_get_api_key(db: Session) -> None:
    user = create_test_user(db)
    org = create_test_organization(db)
    project = create_test_project(db, org.id)

    created_key = api_key_crud.create_api_key(db, org.id, user.id, project.id)
    retrieved_key = api_key_crud.get_api_key(db, created_key.id)

    assert retrieved_key is not None
    assert retrieved_key.id == created_key.id
    assert retrieved_key.key.startswith("ApiKey ")
    assert retrieved_key.project_id == project.id


def test_get_api_key_not_found(db: Session) -> None:
    result = api_key_crud.get_api_key(db, 9999)  # Non-existent ID
    assert result is None


def test_delete_api_key(db: Session) -> None:
    user = create_test_user(db)
    org = create_test_organization(db)
    project = create_test_project(db, org.id)

    api_key = api_key_crud.create_api_key(db, org.id, user.id, project.id)
    api_key_crud.delete_api_key(db, api_key.id)

    deleted_key = db.exec(select(APIKey).where(APIKey.id == api_key.id)).first()

    assert deleted_key is not None
    assert deleted_key.is_deleted is True
    assert deleted_key.deleted_at is not None


def test_delete_api_key_already_deleted(db: Session) -> None:
    user = create_test_user(db)
    org = create_test_organization(db)
    project = create_test_project(db, org.id)

    api_key = api_key_crud.create_api_key(db, org.id, user.id, project.id)
    api_key_crud.delete_api_key(db, api_key.id)

    with pytest.raises(ValueError, match="API key not found or already deleted"):
        api_key_crud.delete_api_key(db, api_key.id)


def test_get_api_key_by_value(db: Session) -> None:
    user = create_test_user(db)
    org = create_test_organization(db)
    project = create_test_project(db, org.id)

    # Create an API key
    api_key = api_key_crud.create_api_key(db, org.id, user.id, project.id)
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


def test_get_api_key_by_project_user(db: Session) -> None:
    user = create_test_user(db)
    org = create_test_organization(db)
    project = create_test_project(db, org.id)

    created_key = api_key_crud.create_api_key(db, org.id, user.id, project.id)
    retrieved_key = api_key_crud.get_api_key_by_project_user(db, project.id, user.id)

    assert retrieved_key is not None
    assert retrieved_key.id == created_key.id
    assert retrieved_key.project_id == project.id
    assert retrieved_key.key.startswith("ApiKey ")


def test_get_api_keys_by_project(db: Session) -> None:
    user = create_test_user(db)
    org = create_test_organization(db)
    project = create_test_project(db, org.id)

    created_key = api_key_crud.create_api_key(db, org.id, user.id, project.id)
    retrieved_keys = api_key_crud.get_api_keys_by_project(db, project.id)

    assert retrieved_keys is not None
    assert len(retrieved_keys) == 1
    retrieved_key = retrieved_keys[0]

    assert retrieved_key.id == created_key.id
    assert retrieved_key.project_id == project.id
    assert retrieved_key.key.startswith("ApiKey ")
