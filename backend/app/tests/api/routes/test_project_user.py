import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.core.config import settings
from app.models import User, Project, ProjectUser, Organization
from app.crud.project_user import add_user_to_project
from app.tests.utils.utils import random_email, get_non_existent_id
from app.tests.utils.user import authentication_token_from_email
from app.core.security import get_password_hash
from app.main import app

client = TestClient(app)


def create_user(db: Session) -> User:
    """Helper function to create a user."""
    user = User(email=random_email(), hashed_password=get_password_hash("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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


def test_add_user_to_project(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    """
    Test adding a user to a project successfully.
    """
    user = create_user(db)
    organization, project = create_organization_and_project(db)

    response = client.post(
        f"{settings.API_V1_STR}/project/users/{user.id}?is_admin=true&project_id={project.id}&organization_id={organization.id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200, response.text
    added_user = response.json()["data"]
    assert added_user["user_id"] == user.id
    assert added_user["project_id"] == project.id
    assert added_user["is_admin"] is True


def test_add_user_not_found(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    """
    Test adding a non-existing user to a project (should return 404).
    """
    organization, project = create_organization_and_project(db)
    user_id = get_non_existent_id(db, User)

    response = client.post(
        f"{settings.API_V1_STR}/project/users/{user_id}?is_admin=false&project_id={project.id}&organization_id={organization.id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"] == "User not found"


def test_add_existing_user_to_project(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    """
    Test adding a user who is already in the project (should return 400).
    """
    user = create_user(db)
    organization, project = create_organization_and_project(db)

    # Add user to project
    project_user = ProjectUser(project_id=project.id, user_id=user.id, is_admin=False)
    db.add(project_user)
    db.commit()

    # Try to add the same user again
    response = client.post(
        f"{settings.API_V1_STR}/project/users/{user.id}?is_admin=false&project_id={project.id}&organization_id={organization.id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 400
    assert "User is already a member of this project" in response.json()["error"]


def test_remove_user_from_project(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    """
    Test removing a user from a project successfully.
    """
    # Create organization and project
    organization, project = create_organization_and_project(db)

    # Create a user
    user = create_user(db)

    # Add user to project
    add_user_to_project(db, project.id, user.id, is_admin=False)

    # Remove user via API
    response = client.delete(
        f"{settings.API_V1_STR}/project/users/{user.id}?project_id={project.id}&organization_id={organization.id}",
        headers=superuser_token_headers,
    )

    # Assertions
    assert response.status_code == 200, response.text
    assert response.json()["data"] == {
        "message": "User removed from project successfully."
    }

    # Ensure user is marked as deleted in the database (Fixed)
    project_user = db.exec(
        select(ProjectUser).where(
            ProjectUser.project_id == project.id,
            ProjectUser.user_id == user.id,
        )
    ).first()

    assert project_user is not None
    assert project_user.is_deleted is True
    assert project_user.deleted_at is not None


def test_normal_user_cannot_add_user(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    """
    Test that a normal user (not admin) cannot add a user to a project.
    """

    organization, project = create_organization_and_project(db)

    normal_user_email = random_email()
    normal_user_token_headers = authentication_token_from_email(
        client=client, email=normal_user_email, db=db
    )

    normal_user = db.exec(select(User).where(User.email == normal_user_email)).first()
    add_user_to_project(db, project.id, normal_user.id, is_admin=False)

    target_user = create_user(db)

    # Normal user attempts to add target user to the project
    response = client.post(
        f"{settings.API_V1_STR}/project/users/{target_user.id}?is_admin=false&project_id={project.id}&organization_id={organization.id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403
    assert (
        response.json()["error"] == "Only project admins or superusers can add users."
    )


def test_normal_user_cannot_remove_user(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    """
    Test that a normal user (not admin) cannot remove a user from a project.
    """
    organization, project = create_organization_and_project(db)

    normal_user_email = random_email()
    normal_user_token_headers = authentication_token_from_email(
        client=client, email=normal_user_email, db=db
    )

    normal_user = db.exec(select(User).where(User.email == normal_user_email)).first()
    add_user_to_project(db, project.id, normal_user.id, is_admin=False)

    target_user = create_user(db)
    add_user_to_project(db, project.id, target_user.id, is_admin=False)

    # Normal user attempts to remove the target user
    response = client.delete(
        f"{settings.API_V1_STR}/project/users/{target_user.id}?project_id={project.id}&organization_id={organization.id}",
        headers=normal_user_token_headers,
    )

    # Assertions
    assert response.status_code == 403
    assert (
        response.json()["error"]
        == "Only project admins or superusers can remove users."
    )
