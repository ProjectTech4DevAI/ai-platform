from sqlmodel import Session

from app.models import (
    Organization,
    Project,
    APIKey,
    Credential,
    OrganizationCreate,
    ProjectCreate,
    CredsCreate,
)
from app.crud import (
    create_organization,
    create_project,
    create_api_key,
    set_creds_for_org,
)
from app.core.providers import Provider
from app.tests.utils.user import create_random_user
from app.tests.utils.utils import random_lower_string, generate_random_string


def create_test_organization(db: Session) -> Organization:
    """
    Creates and returns a test organization with a unique name.

    Persists the organization to the database.
    """
    name = f"TestOrg-{random_lower_string()}"
    org_in = OrganizationCreate(name=name, is_active=True)
    return create_organization(session=db, org_create=org_in)


def create_test_project(db: Session) -> Project:
    """
    Creates and returns a test project under a newly created test organization.

    Persists both the organization and the project to the database.

    """
    org = create_test_organization(db)
    name = f"TestProject-{random_lower_string()}"
    project_description = "This is a test project description."
    project_in = ProjectCreate(
        name=name,
        description=project_description,
        is_active=True,
        organization_id=org.id,
    )
    return create_project(session=db, project_create=project_in)


def create_test_api_key(db: Session) -> APIKey:
    """
    Creates and returns an API key for a test project and test user.

    Persists a test user, organization, project, and API key to the database
    """
    project = create_test_project(db)
    user = create_random_user(db)
    api_key = create_api_key(
        db,
        organization_id=project.organization_id,
        user_id=user.id,
        project_id=project.id,
    )
    return api_key


def test_credential_data(db: Session) -> CredsCreate:
    """
    Returns credential data for a test project in the form of a CredsCreate schema.

    Use this when you just need credential input data without persisting it to the database.
    """
    project = create_test_project(db)
    api_key = "sk-" + generate_random_string(10)
    creds_data = CredsCreate(
        organization_id=project.organization_id,
        project_id=project.id,
        is_active=True,
        credential={
            Provider.OPENAI.value: {
                "api_key": api_key,
                "model": "gpt-4",
                "temperature": 0.7,
            }
        },
    )
    return creds_data


def create_test_credential(db: Session) -> tuple[list[Credential], Project]:
    """
    Creates and returns a test credential for a test project.

    Persists the organization, project, and credential to the database.

    """
    project = create_test_project(db)
    api_key = "sk-" + generate_random_string(10)
    creds_data = CredsCreate(
        organization_id=project.organization_id,
        project_id=project.id,
        is_active=True,
        credential={
            Provider.OPENAI.value: {
                "api_key": api_key,
                "model": "gpt-4",
                "temperature": 0.7,
            }
        },
    )
    return set_creds_for_org(session=db, creds_add=creds_data), project
