import pytest
from sqlmodel import Session
from fastapi import HTTPException

from app.models import Project, ProjectCreate
from app.crud.project import (
    create_project,
    get_project_by_id,
    get_projects_by_organization,
    validate_project,
)
from app.tests.utils.utils import random_lower_string, get_non_existent_id
from app.tests.utils.test_data import create_test_project, create_test_organization


def test_create_project(db: Session) -> None:
    """Test creating a project linked to an organization."""
    org = create_test_organization(db)

    project_name = random_lower_string()
    project_data = ProjectCreate(
        name=project_name,
        description="Test description",
        is_active=True,
        organization_id=org.id,
    )

    project = create_project(session=db, project_create=project_data)

    assert project.id is not None
    assert project.name == project_name
    assert project.description == "Test description"
    assert project.organization_id == org.id


def test_get_project_by_id(db: Session) -> None:
    """Test retrieving a project by ID."""
    project = create_test_project(db)

    fetched_project = get_project_by_id(session=db, project_id=project.id)
    assert fetched_project is not None
    assert fetched_project.id == project.id
    assert fetched_project.name == project.name


def test_get_projects_by_organization(db: Session) -> None:
    """Test retrieving all projects for an organization."""
    org = create_test_organization(db)

    project_1 = create_project(
        session=db,
        project_create=ProjectCreate(
            name="Project 1",
            description="Test project 1",
            is_active=True,
            organization_id=org.id,
        ),
    )

    project_2 = create_project(
        session=db,
        project_create=ProjectCreate(
            name="Project 2",
            description="Test project 2",
            is_active=True,
            organization_id=org.id,
        ),
    )

    projects = get_projects_by_organization(session=db, org_id=org.id)

    assert project_1 in projects
    assert project_2 in projects


def test_get_non_existent_project(db: Session) -> None:
    non_existent_project_id = get_non_existent_id(db, Project)
    fetched_project = get_project_by_id(session=db, project_id=non_existent_project_id)
    assert fetched_project is None


def test_validate_project_success(db: Session) -> None:
    """Test that a valid and active project passes validation."""
    project = create_test_project(db)

    validated_project = validate_project(session=db, project_id=project.id)
    assert validated_project.id == project.id


def test_validate_project_not_found(db: Session) -> None:
    """Test that validation fails when project does not exist."""
    non_existent_project_id = get_non_existent_id(db, Project)
    with pytest.raises(HTTPException, match="Project not found"):
        validate_project(session=db, project_id=non_existent_project_id)


def test_validate_project_inactive(db: Session) -> None:
    """Test that validation fails when project is inactive."""
    org = create_test_organization(db)

    inactive_project = create_project(
        session=db,
        project_create=ProjectCreate(
            name=random_lower_string(),
            description="Inactive project",
            is_active=False,
            organization_id=org.id,
        ),
    )

    with pytest.raises(HTTPException, match="Project is not active"):
        validate_project(session=db, project_id=inactive_project.id)
