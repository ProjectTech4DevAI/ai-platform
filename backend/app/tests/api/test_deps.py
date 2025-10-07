import pytest
import uuid
from sqlmodel import Session, select
from fastapi import HTTPException
from app.api.deps import verify_user_project_organization, get_auth_context
from app.models import (
    User,
    Organization,
    Project,
    ProjectUser,
    UserProjectOrg,
    UserOrganization,
    AuthContext,
)
from app.tests.utils.utils import random_email
from app.core.security import get_password_hash
from app.tests.utils.auth import TestAuthContext
from app.tests.utils.user import authentication_token_from_email, create_random_user
from app.core.config import settings
from app.tests.utils.test_data import create_test_api_key, create_test_project


def create_org_project(
    db: Session, org_active=True, proj_active=True
) -> tuple[Organization, Project]:
    """Helper function to create an organization and a project with customizable active states."""
    org = Organization(name=f"Test Org {uuid.uuid4()}", is_active=org_active)
    db.add(org)
    db.commit()
    db.refresh(org)

    proj = Project(
        name=f"Test Proj {uuid.uuid4()}",
        description="A test project",
        organization_id=org.id,
        is_active=proj_active,
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)

    return org, proj


def create_user(db: Session, is_superuser=False) -> User:
    """Helper function to create a user."""
    user = User(
        email=random_email(),
        hashed_password=get_password_hash("password123"),
        is_superuser=is_superuser,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_org = UserOrganization(**user.model_dump(), organization_id=None)
    return user_org


def test_verify_success(db: Session):
    """Valid user in a project passes verification."""
    user = create_user(db)
    org, proj = create_org_project(db)

    db.add(ProjectUser(project_id=proj.id, user_id=user.id, is_admin=False))
    db.commit()

    result = verify_user_project_organization(db, user, proj.id, org.id)

    assert isinstance(result, UserProjectOrg)
    assert result.project_id == proj.id
    assert result.organization_id == org.id


def test_verify_superuser_bypass(db: Session):
    """Superuser bypasses project membership check."""
    superuser = create_user(db, is_superuser=True)
    org, proj = create_org_project(db)

    result = verify_user_project_organization(db, superuser, proj.id, org.id)

    assert isinstance(result, UserProjectOrg)
    assert result.project_id == proj.id
    assert result.organization_id == org.id


def test_verify_no_org(db: Session):
    """Missing organization results in a 404 error."""
    user = create_user(db)
    invalid_org_id = 9999

    assert (
        db.exec(select(Organization).where(Organization.id == invalid_org_id)).first()
        is None
    )

    with pytest.raises(HTTPException) as exc_info:
        verify_user_project_organization(
            db, user, project_id=1, organization_id=invalid_org_id
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Organization not found"


def test_verify_no_project(db: Session):
    """Missing project results in a 404 error."""
    user = create_user(db)
    org = Organization(name=f"Test Org {uuid.uuid4()}", is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)

    with pytest.raises(HTTPException) as exc_info:
        verify_user_project_organization(db, user, 9999, org.id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Project not found"


def test_verify_project_not_in_org(db: Session):
    """Project not belonging to organization results in a 403 error."""
    user = create_user(db)
    org1, proj1 = create_org_project(db)
    org2, proj2 = create_org_project(db)

    with pytest.raises(HTTPException) as exc_info:
        verify_user_project_organization(db, user, proj2.id, org1.id)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Project does not belong to the organization"


def test_verify_user_not_in_project(db: Session):
    """User not in project results in a 403 error."""
    user = create_user(db)
    org, proj = create_org_project(db)

    with pytest.raises(HTTPException) as exc_info:
        verify_user_project_organization(db, user, proj.id, org.id)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "User is not part of the project"


def test_verify_inactive_organization(db: Session):
    """Inactive organization results in a 400 error."""
    user = create_user(db)
    org, proj = create_org_project(db, org_active=False)

    with pytest.raises(HTTPException) as exc_info:
        verify_user_project_organization(db, user, proj.id, org.id)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Organization is not active"


def test_verify_inactive_project(db: Session):
    """Inactive project results in a 400 error."""
    user = create_user(db)
    org, proj = create_org_project(db, proj_active=False)

    with pytest.raises(HTTPException) as exc_info:
        verify_user_project_organization(db, user, proj.id, org.id)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Project is not active"


class TestGetAuthContext:
    """Test suite for get_auth_context function"""

    def test_get_auth_context_with_valid_api_key(
        self, db: Session, user_api_key: TestAuthContext
    ):
        """Test successful authentication with valid API key"""
        auth_context = get_auth_context(
            session=db,
            token=None,
            api_key=user_api_key.key,
        )

        assert isinstance(auth_context, AuthContext)
        assert auth_context.user == user_api_key.user
        assert auth_context.project == user_api_key.project
        assert auth_context.organization == user_api_key.organization

    def test_get_auth_context_with_invalid_api_key(self, db: Session):
        """Test authentication fails with invalid API key"""
        invalid_api_key = "ApiKey InvalidKeyThatDoesNotExist123456789"

        with pytest.raises(HTTPException) as exc_info:
            get_auth_context(
                session=db,
                token=None,
                api_key=invalid_api_key,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid API Key"

    def test_get_auth_context_with_valid_token(
        self, db: Session, normal_user_token_headers: dict[str, str]
    ):
        """Test successful authentication with valid token"""
        token = normal_user_token_headers["Authorization"].replace("Bearer ", "")
        auth_context = get_auth_context(
            session=db,
            token=token,
            api_key=None,
        )

        # Assert
        assert isinstance(auth_context, AuthContext)
        assert auth_context.user.email == settings.EMAIL_TEST_USER

    def test_get_auth_context_with_invalid_token(self, db: Session):
        """Test authentication fails with invalid token"""
        invalid_token = "invalid.token"

        with pytest.raises(HTTPException) as exc_info:
            get_auth_context(
                session=db,
                token=invalid_token,
                api_key=None,
            )

        assert exc_info.value.status_code == 403

    def test_get_auth_context_with_no_credentials(self, db: Session):
        """Test authentication fails when neither API key nor token is provided"""
        with pytest.raises(HTTPException) as exc_info:
            get_auth_context(
                session=db,
                token=None,
                api_key=None,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid Authorization format"

    def test_get_auth_context_with_inactive_user_via_api_key(self, db: Session):
        """Test authentication fails when API key belongs to inactive user"""
        api_key = create_test_api_key(db)

        user = db.get(User, api_key.user_id)
        user.is_active = False
        db.add(user)
        db.commit()
        db.refresh(user)

        with pytest.raises(HTTPException) as exc_info:
            get_auth_context(
                session=db,
                token=None,
                api_key=api_key.key,
            )

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Inactive user"

    def test_get_auth_context_with_inactive_user_via_token(self, db: Session, client):
        """Test authentication fails when token belongs to inactive user"""
        user = create_random_user(db)
        token_headers = authentication_token_from_email(
            client=client, email=user.email, db=db
        )
        token = token_headers["Authorization"].replace("Bearer ", "")

        user.is_active = False
        db.add(user)
        db.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_auth_context(
                session=db,
                token=token,
                api_key=None,
            )

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Inactive user"

    def test_get_auth_context_with_inactive_organization(
        self, db: Session, user_api_key: TestAuthContext
    ):
        """Test authentication fails when organization is inactive"""
        organization = user_api_key.organization
        organization.is_active = False
        db.add(organization)
        db.commit()
        db.refresh(organization)

        with pytest.raises(HTTPException) as exc_info:
            get_auth_context(
                session=db,
                token=None,
                api_key=user_api_key.key,
            )

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Inactive Organization"

    def test_get_auth_context_with_inactive_project(
        self, db: Session, user_api_key: TestAuthContext
    ):
        """Test authentication fails when project is inactive"""
        project = user_api_key.project
        project.is_active = False
        db.add(project)
        db.commit()
        db.refresh(project)

        with pytest.raises(HTTPException) as exc_info:
            get_auth_context(
                session=db,
                token=None,
                api_key=user_api_key.key,
            )

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Inactive Project"
