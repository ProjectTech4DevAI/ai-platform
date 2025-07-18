from sqlmodel import Session, select

from app.crud import api_key as api_key_crud
from app.models import APIKey
from app.tests.utils.utils import get_non_existent_id
from app.tests.utils.user import create_random_user
from app.tests.utils.test_data import create_test_api_key, create_test_project


def test_create_api_key(db: Session) -> None:
    user = create_random_user(db)
    project = create_test_project(db)

    api_key = api_key_crud.create_api_key(
        db, project.organization_id, user.id, project.id
    )

    assert api_key.key.startswith("ApiKey ")
    assert len(api_key.key) > 32
    assert api_key.organization_id == project.organization_id
    assert api_key.user_id == user.id
    assert api_key.project_id == project.id


def test_get_api_key(db: Session) -> None:
    api_key = create_test_api_key(db)
    retrieved_key = api_key_crud.get_api_key(db, api_key.id)

    assert retrieved_key is not None
    assert retrieved_key.id == api_key.id
    assert retrieved_key.key.startswith("ApiKey ")
    assert retrieved_key.project_id == api_key.project_id


def test_get_api_key_not_found(db: Session) -> None:
    api_key_id = get_non_existent_id(db, APIKey)
    result = api_key_crud.get_api_key(db, api_key_id)
    assert result is None


def test_delete_api_key(db: Session) -> None:
    api_key = create_test_api_key(db)
    api_key_crud.delete_api_key(db, api_key.id)

    deleted_key = db.exec(select(APIKey).where(APIKey.id == api_key.id)).first()

    assert deleted_key is not None
    assert deleted_key.is_deleted is True
    assert deleted_key.deleted_at is not None


def test_get_api_key_by_value(db: Session) -> None:
    api_key = create_test_api_key(db)
    raw_key = api_key.key

    # Test retrieving the API key by its value
    retrieved_key = api_key_crud.get_api_key_by_value(db, raw_key)

    assert retrieved_key is not None
    assert retrieved_key.id == api_key.id
    assert retrieved_key.organization_id == api_key.organization_id
    assert retrieved_key.user_id == api_key.user_id
    # The key should be in its original format
    assert retrieved_key.key == raw_key  # Should be exactly the same key
    assert retrieved_key.key.startswith("ApiKey ")
    assert len(retrieved_key.key) > 32


def test_get_api_key_by_project_user(db: Session) -> None:
    user = create_random_user(db)
    project = create_test_project(db)

    created_key = api_key_crud.create_api_key(
        db, project.organization_id, user.id, project.id
    )
    retrieved_key = api_key_crud.get_api_key_by_project_user(db, project.id, user.id)

    assert retrieved_key is not None
    assert retrieved_key.id == created_key.id
    assert retrieved_key.project_id == project.id
    assert retrieved_key.key.startswith("ApiKey ")


def test_get_api_keys_by_project(db: Session) -> None:
    user = create_random_user(db)
    project = create_test_project(db)

    created_key = api_key_crud.create_api_key(
        db, project.organization_id, user.id, project.id
    )

    retrieved_keys = api_key_crud.get_api_keys_by_project(db, project.id)

    assert retrieved_keys is not None
    assert len(retrieved_keys) == 1
    retrieved_key = retrieved_keys[0]

    assert retrieved_key.id == created_key.id
    assert retrieved_key.project_id == project.id
    assert retrieved_key.key.startswith("ApiKey ")


def test_get_api_key_by_user_id(db: Session) -> None:
    user = create_random_user(db)
    project = create_test_project(db)

    created_key = api_key_crud.create_api_key(
        db, project.organization_id, user.id, project.id
    )

    retrieved_key = api_key_crud.get_api_key_by_user_id(db, user.id)

    assert retrieved_key is not None

    assert retrieved_key.id == created_key.id
    assert retrieved_key.user_id == user.id
    assert retrieved_key.key.startswith("ApiKey ")
