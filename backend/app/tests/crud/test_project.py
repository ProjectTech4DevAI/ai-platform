import pytest
from sqlmodel import SQLModel, Session, create_engine

from app.models import Project, ProjectCreate, Organization
from app.crud.project import (
    create_project,
    get_project_by_id,
    get_projects_by_organization,
    validate_project,
)
from app.tests.utils.utils import random_lower_string


def test_create_project(db: Session) -> None:
    """Test creating a project linked to an organization."""
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

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
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    project_name = random_lower_string()
    project_data = ProjectCreate(
        name=project_name, description="Test", organization_id=org.id
    )

    project = create_project(session=db, project_create=project_data)

    fetched_project = get_project_by_id(session=db, project_id=project.id)
    assert fetched_project is not None
    assert fetched_project.id == project.id
    assert fetched_project.name == project.name


def test_get_projects_by_organization(db: Session) -> None:
    """Test retrieving all projects for an organization."""
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    project_1 = create_project(
        session=db,
        project_create=ProjectCreate(
            name=random_lower_string(), organization_id=org.id
        ),
    )
    project_2 = create_project(
        session=db,
        project_create=ProjectCreate(
            name=random_lower_string(), organization_id=org.id
        ),
    )

    projects = get_projects_by_organization(session=db, org_id=org.id)

    assert len(projects) == 2
    assert project_1 in projects
    assert project_2 in projects


def test_get_non_existent_project(db: Session) -> None:
    """Test retrieving a non-existent project should return None."""
    fetched_project = get_project_by_id(session=db, project_id=999)
    assert fetched_project is None


def test_validate_project_success(db: Session) -> None:
    """Test that a valid and active project passes validation."""
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    project = create_project(
        session=db,
        project_create=ProjectCreate(
            name=random_lower_string(),
            description="Valid project",
            is_active=True,
            organization_id=org.id,
        ),
    )

    validated_project = validate_project(session=db, project_id=project.id)
    assert validated_project.id == project.id
