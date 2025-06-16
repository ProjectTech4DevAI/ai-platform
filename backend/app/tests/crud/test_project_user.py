import uuid
from sqlmodel import Session, select
from datetime import datetime
import pytest

from app.crud import project_user as project_user_crud
from app.models import ProjectUser, ProjectUserPublic, User, Project, Organization
from app.tests.utils.utils import random_email, get_non_existent_id
from app.core.security import get_password_hash


def create_organization_and_project(db: Session) -> tuple[Organization, Project]:
    """Helper function to create an organization and a project."""

    organization = Organization(
        name=f"Test Organization {uuid.uuid4()}", is_active=True
    )
    db.add(organization)
    db.commit()
    db.refresh(organization)

    # Ensure project with unique name
    project_name = f"Test Project {uuid.uuid4()}"  # Ensuring unique project name
    project = Project(
        name=project_name,
        description="A test project",
        organization_id=organization.id,
        is_active=True,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    return organization, project


def test_is_project_admin(db: Session) -> None:
    organization, project = create_organization_and_project(db)

    user = User(email=random_email(), hashed_password=get_password_hash("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)

    project_user = ProjectUser(project_id=project.id, user_id=user.id, is_admin=True)
    db.add(project_user)
    db.commit()
    db.refresh(project_user)

    assert project_user_crud.is_project_admin(db, user.id, project.id) is True


def test_add_user_to_project(db: Session) -> None:
    organization, project = create_organization_and_project(db)

    user = User(email=random_email(), hashed_password=get_password_hash("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)

    project_user = project_user_crud.add_user_to_project(
        db, project.id, user.id, is_admin=True
    )

    assert project_user.user_id == user.id
    assert project_user.project_id == project.id
    assert project_user.is_admin is True


def test_add_user_to_project_duplicate(db: Session) -> None:
    organization, project = create_organization_and_project(db)

    user = User(email=random_email(), hashed_password=get_password_hash("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)

    project_user_crud.add_user_to_project(db, project.id, user.id)

    with pytest.raises(ValueError, match="User is already a member of this project"):
        project_user_crud.add_user_to_project(db, project.id, user.id)


def test_remove_user_from_project(db: Session) -> None:
    organization, project = create_organization_and_project(db)

    user = User(email=random_email(), hashed_password=get_password_hash("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)

    # Add user to project
    project_user_crud.add_user_to_project(db, project.id, user.id)

    # Remove user from project
    project_user_crud.remove_user_from_project(db, project.id, user.id)

    # Retrieve project user with both project_id and user_id
    project_user = db.exec(
        select(ProjectUser).where(
            ProjectUser.project_id == project.id, ProjectUser.user_id == user.id
        )
    ).first()

    assert project_user is not None  # Ensure the record still exists (soft delete)
    assert project_user.is_deleted is True
    assert project_user.deleted_at is not None


def test_remove_user_from_project_not_member(db: Session) -> None:
    organization, project = create_organization_and_project(db)

    project_id = project.id
    user_id = get_non_existent_id(db, User)

    with pytest.raises(
        ValueError, match="User is not a member of this project or already removed"
    ):
        project_user_crud.remove_user_from_project(db, project_id, user_id)


def test_get_users_by_project(db: Session) -> None:
    organization, project = create_organization_and_project(db)

    user1 = User(email=random_email(), hashed_password=get_password_hash("password123"))
    user2 = User(email=random_email(), hashed_password=get_password_hash("password123"))

    db.add_all([user1, user2])
    db.commit()
    db.refresh(user1)
    db.refresh(user2)

    project_user_crud.add_user_to_project(db, project.id, user1.id)
    project_user_crud.add_user_to_project(db, project.id, user2.id)

    users, total_count = project_user_crud.get_users_by_project(
        db, project.id, skip=0, limit=10
    )

    assert total_count == 2
    assert len(users) == 2
