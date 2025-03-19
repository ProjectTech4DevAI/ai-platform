import uuid
from sqlmodel import Session, select
from datetime import datetime
import pytest

from app.crud import project_user as project_user_crud
from app.models import ProjectUser, ProjectUserPublic, User, Project
from app.tests.utils.utils import random_email
from app.core.security import get_password_hash


def test_is_project_admin(db: Session) -> None:
    user = User(email=random_email(), hashed_password=get_password_hash("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)

    # Ensure the project exists
    project = Project(name="Test Project", description="A test project", organization_id=1)
    db.add(project)
    db.commit()
    db.refresh(project)

    project_user = ProjectUser(project_id=project.id, user_id=user.id, is_admin=True)
    db.add(project_user)
    db.commit()
    db.refresh(project_user)

    assert project_user_crud.is_project_admin(db, user.id, project.id) is True


def test_add_user_to_project(db: Session) -> None:
    user = User(email=random_email(), hashed_password=get_password_hash("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)

    # Ensure the project exists
    project = Project(name="Test Project", description="A test project", organization_id=1)
    db.add(project)
    db.commit()
    db.refresh(project)

    project_user = project_user_crud.add_user_to_project(db, project.id, user.id, is_admin=True)

    assert project_user.user_id == user.id
    assert project_user.project_id == project.id
    assert project_user.is_admin is True


def test_add_user_to_project_duplicate(db: Session) -> None:
    user = User(email=random_email(), hashed_password=get_password_hash("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)

    # Ensure the project exists
    project = Project(name="Test Project", description="A test project", organization_id=1)
    db.add(project)
    db.commit()
    db.refresh(project)

    project_user_crud.add_user_to_project(db, project.id, user.id)

    with pytest.raises(ValueError, match="User is already a member of this project"):
        project_user_crud.add_user_to_project(db, project.id, user.id)


def test_remove_user_from_project(db: Session) -> None:
    user = User(email=random_email(), hashed_password=get_password_hash("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)

    # Ensure the project exists
    project = Project(name="Test Project", description="A test project", organization_id=1)
    db.add(project)
    db.commit()
    db.refresh(project)

    # Add user to project
    project_user_crud.add_user_to_project(db, project.id, user.id)

    # Remove user from project
    project_user_crud.remove_user_from_project(db, project.id, user.id)

    # Retrieve project user with both project_id and user_id
    project_user = db.exec(
        select(ProjectUser).where(
            ProjectUser.project_id == project.id,
            ProjectUser.user_id == user.id
        )
    ).first()

    assert project_user is not None  # Ensure the record still exists (soft delete)
    assert project_user.is_deleted is True
    assert project_user.deleted_at is not None


def test_remove_user_from_project_not_member(db: Session) -> None:
    # Ensure the project exists
    project = Project(name="Test Project", description="A test project", organization_id=1)
    db.add(project)
    db.commit()
    db.refresh(project)

    project_id = project.id
    user_id = uuid.uuid4()

    with pytest.raises(ValueError, match="User is not a member of this project or already removed"):
        project_user_crud.remove_user_from_project(db, project_id, user_id)


def test_get_users_by_project(db: Session) -> None:
    # Ensure the project exists
    project = Project(name="Test Project", description="A test project", organization_id=1)
    db.add(project)
    db.commit()
    db.refresh(project)

    user1 = User(email=random_email(), hashed_password=get_password_hash("password123"))
    user2 = User(email=random_email(), hashed_password=get_password_hash("password123"))

    db.add_all([user1, user2])
    db.commit()
    db.refresh(user1)
    db.refresh(user2)

    project_user_crud.add_user_to_project(db, project.id, user1.id)
    project_user_crud.add_user_to_project(db, project.id, user2.id)

    users, total_count = project_user_crud.get_users_by_project(db, project.id, skip=0, limit=10)

    assert total_count == 2
    assert len(users) == 2
