import importlib
import logging
import os
import random
import string
from typing import TypeVar
from uuid import UUID

from dotenv import load_dotenv
from fastapi.testclient import TestClient
from pydantic import EmailStr
from sqlmodel import Session, create_engine, select

from app.core import config
from app.core.config import settings
from app.crud.api_key import get_api_key_by_user_id, get_api_key_by_value
from app.crud.user import get_user_by_email
from app.models import APIKeyPublic, Assistant, Organization, Project

logger = logging.getLogger(__name__)

T = TypeVar("T")


def random_lower_string() -> str:
    """Generate a random lowercase string of 32 characters."""
    return "".join(random.choices(string.ascii_lowercase, k=32))


def generate_random_string(length: int = 10) -> str:
    """Generate a random string of specified length."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def random_email() -> str:
    """Generate a random email address."""
    return f"{random_lower_string()}@{random_lower_string()}.com"


def get_superuser_token_headers(client: TestClient) -> dict[str, str]:
    """Get authentication headers for superuser."""
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}
    return headers


def get_api_key_by_email(db: Session, email: EmailStr) -> APIKeyPublic:
    """Get API key for a user by their email address."""
    user = get_user_by_email(session=db, email=email)
    api_key = get_api_key_by_user_id(db, user_id=user.id)
    return api_key


def get_user_id_by_email(db: Session) -> int:
    """Get user ID for the test user email."""
    user = get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    return user.id


def get_user_from_api_key(db: Session, api_key_headers: dict[str, str]) -> APIKeyPublic:
    """Get API key object from API key headers."""
    key_value = api_key_headers["X-API-KEY"]
    api_key = get_api_key_by_value(db, api_key_value=key_value)
    if api_key is None:
        raise ValueError("Invalid API Key")
    return api_key


def get_non_existent_id(session: Session, model: type[T]) -> int:
    """Get an ID that doesn't exist in the database for the given model."""
    result = session.exec(select(model.id).order_by(model.id.desc())).first()
    return (result or 0) + 1


def get_project(session: Session, name: str | None = None) -> Project:
    """
    Retrieve an active project from the database.

    If a project name is provided, fetch the active project with that name.
    If no name is provided, fetch any random project.
    """
    if name:
        statement = (
            select(Project).where(Project.name == name, Project.is_active).limit(1)
        )
    else:
        statement = select(Project).where(Project.is_active).limit(1)

    project = session.exec(statement).first()

    if not project:
        raise ValueError("No active projects found")

    return project


def load_environment(env_test_path: str) -> None:
    """
    Load test environment variables from the specified file.

    Args:
        env_test_path: Path to the test environment file.

    Raises:
        ValueError: If required PostgreSQL credentials are missing.
        RuntimeError: If the database name doesn't contain 'test'.
    """
    if os.path.exists(env_test_path):
        load_dotenv(env_test_path, override=True)

        required_vars = [
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_SERVER",
            "POSTGRES_PORT",
            "POSTGRES_DB",
        ]

        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            raise ValueError(
                f"Missing the following PostgreSQL credentials in {env_test_path}: "
                f"{', '.join(missing_vars)}"
            )

        db_name = os.getenv("POSTGRES_DB", "").lower()
        if "test" not in db_name:
            raise RuntimeError(
                f"Connected to database '{db_name}', which doesn't appear to be a "
                f"test database"
            )

        # Reload settings to reflect the new environment variables
        importlib.reload(config)

        # Recreate the engine with the updated settings
        from app.core.db import engine

        # Dispose of the old engine
        engine.dispose()

        # Create a new engine with updated settings
        new_engine = create_engine(
            str(config.settings.SQLALCHEMY_DATABASE_URI),
            pool_size=20 if config.settings.ENVIRONMENT == "local" else 5,
            max_overflow=30 if config.settings.ENVIRONMENT == "local" else 10,
            pool_pre_ping=True,
            pool_recycle=300,
        )

        # Replace the engine in the db module
        import app.core.db

        app.core.db.engine = new_engine

    else:
        logger.warning(
            f"{env_test_path} not found. Using default environment settings."
        )


def get_assistant(session: Session, name: str | None = None) -> Assistant:
    """
    Retrieve an active assistant from the database.

    If an assistant name is provided, fetch the active assistant with that name.
    If no name is provided, fetch any random assistant.
    """
    if name:
        statement = (
            select(Assistant)
            .where(Assistant.name == name, Assistant.is_deleted == False)
            .limit(1)
        )
    else:
        statement = select(Assistant).where(Assistant.is_deleted == False).limit(1)

    assistant = session.exec(statement).first()

    if not assistant:
        raise ValueError("No active assistants found")

    return assistant


def get_organization(session: Session, name: str | None = None) -> Organization:
    """
    Retrieve an active organization from the database.

    If an organization name is provided, fetch the active organization with that name.
    If no name is provided, fetch any random organization.
    """
    if name:
        statement = (
            select(Organization)
            .where(Organization.name == name, Organization.is_active)
            .limit(1)
        )
    else:
        statement = select(Organization).where(Organization.is_active).limit(1)

    organization = session.exec(statement).first()

    if not organization:
        raise ValueError("No active organizations found")

    return organization


class SequentialUuidGenerator:
    """Generate sequential UUIDs for testing purposes."""

    def __init__(self, start: int = 0) -> None:
        """Initialize the generator with a starting value."""
        self.start = start

    def __iter__(self) -> "SequentialUuidGenerator":
        """Return self as an iterator."""
        return self

    def __next__(self) -> UUID:
        """Generate the next UUID in sequence."""
        uu_id = UUID(int=self.start)
        self.start += 1
        return uu_id

    def peek(self) -> UUID:
        """Peek at the next UUID without advancing the sequence."""
        return UUID(int=self.start)
