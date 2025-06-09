import uuid
import json
from pathlib import Path
from sqlmodel import Session, delete, text
from app.models import Organization, Project, User, APIKey
from app.core.security import get_password_hash, encrypt_api_key
from app.core.db import engine
import logging
from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional


# Pydantic models for data validation
class OrgData(BaseModel):
    id: int
    name: str
    is_active: bool


class ProjectData(BaseModel):
    id: int
    name: str
    description: str
    is_active: bool
    organization_id: int


class UserData(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    is_superuser: bool
    is_active: bool
    password: str


class APIKeyData(BaseModel):
    id: int
    organization_id: int
    user_id: str
    api_key: str
    is_deleted: bool
    deleted_at: Optional[str] = None
    created_at: Optional[str] = None


def load_seed_data() -> dict:
    """Load seed data from JSON file."""
    json_path = Path(__file__).parent / "seed_data.json"
    try:
        with open(json_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Error: Seed data file not found at {json_path}")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Error: Failed to decode JSON from {json_path}: {e}")
        raise


def create_organization(session: Session, org_data_raw: dict) -> Organization:
    """Create an organization from data."""
    try:
        org_data = OrgData.model_validate(org_data_raw)
        logging.info(f"Creating organization: {org_data.name}")
        organization = Organization(
            id=org_data.id, name=org_data.name, is_active=org_data.is_active
        )
        session.add(organization)
        return organization
    except Exception as e:
        logging.error(f"Error creating organization: {e}")
        raise


def create_project(session: Session, project_data_raw: dict) -> Project:
    """Create a project from data."""
    try:
        project_data = ProjectData.model_validate(project_data_raw)
        logging.info(f"Creating project: {project_data.name}")
        project = Project(
            id=project_data.id,
            name=project_data.name,
            description=project_data.description,
            is_active=project_data.is_active,
            organization_id=project_data.organization_id,
        )
        session.add(project)
        return project
    except Exception as e:
        logging.error(f"Error creating project: {e}")
        raise


def create_user(session: Session, user_data_raw: dict) -> User:
    """Create a user from data."""
    try:
        user_data = UserData.model_validate(user_data_raw)
        logging.info(f"Creating user: {user_data.email}")
        hashed_password = get_password_hash(user_data.password)
        user = User(
            id=uuid.UUID(user_data.id),
            email=user_data.email,
            full_name=user_data.full_name,
            is_superuser=user_data.is_superuser,
            is_active=user_data.is_active,
            hashed_password=hashed_password,
        )
        session.add(user)
        return user
    except Exception as e:
        logging.error(f"Error creating user: {e}")
        raise


def create_api_key(session: Session, api_key_data_raw: dict) -> APIKey:
    """Create an API key from data."""
    try:
        api_key_data = APIKeyData.model_validate(api_key_data_raw)
        logging.info(f"Creating API key for user {api_key_data.user_id}")
        encrypted_api_key = encrypt_api_key(api_key_data.api_key)
        api_key = APIKey(
            id=api_key_data.id,
            organization_id=api_key_data.organization_id,
            user_id=uuid.UUID(api_key_data.user_id),
            key=encrypted_api_key,
            is_deleted=api_key_data.is_deleted,
            deleted_at=api_key_data.deleted_at,
        )
        if api_key_data.created_at:
            api_key.created_at = datetime.fromisoformat(
                api_key_data.created_at.replace("Z", "+00:00")
            )
        session.add(api_key)
        return api_key
    except Exception as e:
        logging.error(f"Error creating API key: {e}")
        raise


def clear_database(session: Session) -> None:
    """Clear all seeded data from the database."""
    logging.info("Clearing existing data...")
    session.exec(delete(APIKey))
    session.exec(delete(Project))
    session.exec(delete(Organization))
    session.exec(delete(User))
    session.commit()
    logging.info("Existing data cleared.")


def reset_sequences(session: Session):
    """Reset PostgreSQL sequences after manual ID insertion."""
    tables_and_seqs = {
        "organization": "organization_id_seq",
        "project": "project_id_seq",
        "apikey": "apikey_id_seq",
    }

    for table, seq in tables_and_seqs.items():
        stmt = text(
            f"""
            SELECT setval('{seq}',
            COALESCE((SELECT MAX(id) FROM {table}), 1) + 1, false);
        """
        )
        session.exec(stmt)
        logging.info(f"Reset sequence {seq} for table {table}")
    session.commit()
    logging.info(f"Reset sequence Successfully for all tables.")


def seed_database(session: Session) -> None:
    """Seed the database with initial data."""
    logging.info("Starting database seeding...")

    try:
        # Clear existing data first
        clear_database(session)

        # Load seed data from JSON
        seed_data = load_seed_data()

        # Create organizations
        organizations = []
        for org_data in seed_data["organization"]:
            organization = create_organization(session, org_data)
            organizations.append(organization)
            logging.info(
                f"Created organization: {organization.name} (ID: {organization.id})"
            )

        # Create users
        users = []
        for user_data in seed_data["users"]:
            user = create_user(session, user_data)
            users.append(user)
            logging.info(f"Created user: {user.email} (ID: {user.id})")

        # Create projects
        projects = []
        for project_data in seed_data["projects"]:
            project = create_project(session, project_data)
            projects.append(project)
            logging.info(f"Created project: {project.name} (ID: {project.id})")

        # Create API keys
        api_keys = []
        for api_key_data in seed_data["apikeys"]:
            api_key = create_api_key(session, api_key_data)
            api_keys.append(api_key)
            logging.info(f"Created API key (ID: {api_key.id})")

        logging.info("Database seeding completed successfully!")
        session.commit()

        # Reset sequences after manual ID insertion
        reset_sequences(session)
    except Exception as e:
        logging.error(f"Error during seeding: {e}")
        session.rollback()
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("Initializing database session...")
    with Session(engine) as session:
        try:
            seed_database(session)
            logging.info("Database seeded successfully!")
        except Exception as e:
            logging.error(f"Error seeding database: {e}")
            session.rollback()
