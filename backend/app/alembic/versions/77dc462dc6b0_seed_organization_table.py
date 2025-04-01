"""seed organization table

Revision ID: 77dc462dc6b0
Revises: 0f205e3779ee
Create Date: 2025-03-26 19:58:51.004555

"""
from app.core.config import settings
from alembic import op
import secrets
from sqlmodel import Session
# Adjust the import based on your actual structure
from app.models import Organization, Project, User, APIKey
from passlib.context import CryptContext  # To hash passwords securely

# revision identifiers, used by Alembic.
revision = '77dc462dc6b0'
down_revision = '0f205e3779ee'
branch_labels = None
depends_on = None

# Use op.get_bind() to get the session from the Alembic context
bind = op.get_bind()
# Create a session from the Alembic bind context
session = Session(bind=bind)

# Setup password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_organization(session: Session, name: str) -> Organization:
    """Create and return an organization."""
    organization = Organization(name=name, is_active=True)
    session.add(organization)
    session.commit()
    return organization


def create_projects(session: Session, organization: Organization):
    """Create projects for an organization."""
    projects = [
        Project(name="Glific", description="Two way communication platform",
                organization_id=organization.id),
        Project(name="Dalgo", description="Data platform for the social sector",
                organization_id=organization.id)
    ]
    session.add_all(projects)
    session.commit()


def create_user(session: Session, is_super: bool = True) -> User:
    """Create a user and return the user."""
    if is_super:
        email = settings.FIRST_SUPERUSER
        password = settings.FIRST_SUPERUSER_PASSWORD
        full_name = "SUPERUSER"
    else:
        email = "admin@example.com"
        password = "admin123"
        full_name = "ADMIN"

    hashed_password = hash_password(password)
    user = User(
        email=email,
        is_active=True,
        is_superuser=is_super,
        full_name=full_name,
        hashed_password=hashed_password
    )
    session.add(user)
    session.commit()
    return user


def create_api_key(session: Session, user: User, organization: Organization) -> APIKey:
    """Create and return an API key for the user and organization."""
    api_key = APIKey(
        user_id=user.id,
        organization_id=organization.id,
        key='ApiKey '+secrets.token_urlsafe(32)
    )
    session.add(api_key)
    session.commit()
    return api_key


def seed_organizations_and_projects(session: Session):
    """Seed organizations, projects, users, and API keys."""
    organization = create_organization(session, name="Project Tech4dev")
    create_projects(session, organization)

    # Create superuser and their API key
    superuser = create_user(session, is_super=True)
    create_api_key(session, superuser, organization)

    # Create regular user and their API key
    regular_user = create_user(session, is_super=False)
    create_api_key(session, regular_user, organization)


def delete_all_data(session: Session):
    """Delete all records from Organization, Project, User, and APIKey."""
    statement = Organization.__table__.delete()
    session.exec(statement)
    session.commit()

    statement = Project.__table__.delete()
    session.exec(statement)
    session.commit()

    statement = User.__table__.delete()
    session.exec(statement)
    session.commit()

    statement = APIKey.__table__.delete()
    session.exec(statement)
    session.commit()


def upgrade() -> None:
    """Upgrade function to apply migrations."""
    delete_all_data(session)
    seed_organizations_and_projects(session)


def downgrade() -> None:
    """Downgrade function to revert migrations."""
    delete_all_data(session)
