import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, EmailStr
from sqlmodel import Session, delete, select

from app.core.db import engine
from app.core import settings
from app.core.security import encrypt_api_key, get_password_hash
from app.models import APIKey, Organization, Project, User, Credential, Assistant


# Pydantic models for data validation
class OrgData(BaseModel):
    name: str
    is_active: bool


class ProjectData(BaseModel):
    name: str
    description: str
    is_active: bool
    organization_name: str


class UserData(BaseModel):
    email: EmailStr
    full_name: str
    is_superuser: bool
    is_active: bool
    password: str


class APIKeyData(BaseModel):
    organization_name: str
    project_name: str
    user_email: EmailStr
    api_key: str
    is_deleted: bool
    deleted_at: Optional[str] = None
    created_at: Optional[str] = None


class CredentialData(BaseModel):
    is_active: bool
    provider: str
    credential: str
    organization_name: str
    project_name: str
    deleted_at: Optional[str] = None


class AssistantData(BaseModel):
    assistant_id: str
    name: str
    instructions: str
    model: str
    vector_store_ids: list[str]
    temperature: float
    max_num_results: int
    project_name: str
    organization_name: str


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
        organization = Organization(name=org_data.name, is_active=org_data.is_active)
        session.add(organization)
        session.flush()  # Ensure ID is assigned
        return organization
    except Exception as e:
        logging.error(f"Error creating organization: {e}")
        raise


def create_project(session: Session, project_data_raw: dict) -> Project:
    """Create a project from data."""
    try:
        project_data = ProjectData.model_validate(project_data_raw)
        logging.info(f"Creating project: {project_data.name}")
        # Query organization ID by name
        organization = session.exec(
            select(Organization).where(
                Organization.name == project_data.organization_name
            )
        ).first()
        if not organization:
            raise ValueError(
                f"Organization '{project_data.organization_name}' not found"
            )
        project = Project(
            name=project_data.name,
            description=project_data.description,
            is_active=project_data.is_active,
            organization_id=organization.id,
        )
        session.add(project)
        session.flush()  # Ensure ID is assigned
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
            email=user_data.email,
            full_name=user_data.full_name,
            is_superuser=user_data.is_superuser,
            is_active=user_data.is_active,
            hashed_password=hashed_password,
        )
        session.add(user)
        session.flush()  # Ensure ID is assigned
        return user
    except Exception as e:
        logging.error(f"Error creating user: {e}")
        raise


def create_api_key(session: Session, api_key_data_raw: dict) -> APIKey:
    """Create an API key from data."""
    try:
        api_key_data = APIKeyData.model_validate(api_key_data_raw)
        logging.info(f"Creating API key for user {api_key_data.user_email}")
        # Query organization ID by name
        organization = session.exec(
            select(Organization).where(
                Organization.name == api_key_data.organization_name
            )
        ).first()
        if not organization:
            raise ValueError(
                f"Organization '{api_key_data.organization_name}' not found"
            )
        project = session.exec(
            select(Project).where(Project.name == api_key_data.project_name)
        ).first()
        if not project:
            raise ValueError(f"Project '{api_key_data.project_name}' not found")
        # Query user ID by email
        user = session.exec(
            select(User).where(User.email == api_key_data.user_email)
        ).first()
        if not user:
            raise ValueError(f"User '{api_key_data.user_email}' not found")
        encrypted_api_key = encrypt_api_key(api_key_data.api_key)
        api_key = APIKey(
            organization_id=organization.id,
            project_id=project.id,
            user_id=user.id,
            key=encrypted_api_key,
            is_deleted=api_key_data.is_deleted,
            deleted_at=api_key_data.deleted_at,
        )
        if api_key_data.created_at:
            api_key.created_at = datetime.fromisoformat(
                api_key_data.created_at.replace("Z", "+00:00")
            )
        session.add(api_key)
        session.flush()  # Ensure ID is assigned
        return api_key
    except Exception as e:
        logging.error(f"Error creating API key: {e}")
        raise


def create_credential(session: Session, credential_data_raw: dict) -> Credential:
    """Create a credential from data."""
    try:
        credential_data = CredentialData.model_validate(credential_data_raw)
        logging.info(f"Creating credential for provider: {credential_data.provider}")

        # Query organization ID by name
        organization = session.exec(
            select(Organization).where(
                Organization.name == credential_data.organization_name
            )
        ).first()
        if not organization:
            raise ValueError(
                f"Organization '{credential_data.organization_name}' not found"
            )

        # Query organization ID by name
        project = session.exec(
            select(Project).where(Project.name == credential_data.project_name)
        ).first()
        if not project:
            raise ValueError(f"Project '{credential_data.project_name}' not found")

        # Encrypt the credential data
        encrypted_credential = encrypt_api_key(credential_data.credential)

        credential = Credential(
            is_active=credential_data.is_active,
            provider=credential_data.provider,
            credential=encrypted_credential,
            organization_id=organization.id,
            project_id=project.id,
            deleted_at=credential_data.deleted_at,
        )
        session.add(credential)
        session.flush()  # Ensure ID is assigned
        return credential
    except Exception as e:
        logging.error(f"Error creating credential: {e}")
        raise


def create_assistant(session: Session, assistant_data_raw: dict) -> Assistant:
    """Create an assistant from data."""
    try:
        assistant_data = AssistantData.model_validate(assistant_data_raw)
        logging.info(f"Creating assistant: {assistant_data.name}")

        # Query organization ID by name
        organization = session.exec(
            select(Organization).where(
                Organization.name == assistant_data.organization_name
            )
        ).first()
        if not organization:
            raise ValueError(
                f"Organization '{assistant_data.organization_name}' not found"
            )

        # Query project ID by name
        project = session.exec(
            select(Project).where(Project.name == assistant_data.project_name)
        ).first()
        if not project:
            raise ValueError(f"Project '{assistant_data.project_name}' not found")

        assistant = Assistant(
            assistant_id=assistant_data.assistant_id,
            name=assistant_data.name,
            instructions=assistant_data.instructions,
            model=assistant_data.model,
            vector_store_ids=assistant_data.vector_store_ids,
            temperature=assistant_data.temperature,
            max_num_results=assistant_data.max_num_results,
            organization_id=organization.id,
            project_id=project.id,
        )
        session.add(assistant)
        session.flush()  # Ensure ID is assigned
        return assistant
    except Exception as e:
        logging.error(f"Error creating assistant: {e}")
        raise


def clear_database(session: Session) -> None:
    """Clear all seeded data from the database."""
    logging.info("Clearing existing data...")
    session.exec(delete(Assistant))
    session.exec(delete(APIKey))
    session.exec(delete(Project))
    session.exec(delete(Organization))
    session.exec(delete(User))
    session.exec(delete(Credential))
    session.commit()
    logging.info("Existing data cleared.")


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
            # Directly map the emails from environment variables based on the user role
            if user_data["full_name"] == "SUPERUSER":
                user_data["email"] = settings.FIRST_SUPERUSER
            elif user_data["full_name"] == "ADMIN":
                user_data["email"] = settings.EMAIL_TEST_USER
            else:
                # If the user is not SUPERUSER or ADMIN, allow manual email assignment
                if "email" not in user_data:
                    logging.warning(
                        f"Email not provided for user {user_data['full_name']}. Skipping user creation."
                    )
                    continue  # Skip if no email is provided for new users
                logging.info(
                    f"Email manually provided for user: {user_data['full_name']}"
                )

            # Create the user in the database
            user = create_user(session, user_data)
            users.append(user)
            logging.info(f"Created user: {user.email} (ID: {user.id})")

        # Create projects
        projects = []
        for project_data in seed_data["projects"]:
            project = create_project(session, project_data)
            projects.append(project)
            logging.info(f"Created project: {project.name} (ID: {project.id})")

        for api_key_data in seed_data["apikeys"]:
            if api_key_data["user_email"] == "{{SUPERUSER_EMAIL}}":
                api_key_data["user_email"] = settings.FIRST_SUPERUSER
            elif api_key_data["user_email"] == "{{ADMIN_EMAIL}}":
                api_key_data["user_email"] = settings.EMAIL_TEST_USER

        # Create API keys
        api_keys = []
        for api_key_data in seed_data["apikeys"]:
            api_key = create_api_key(session, api_key_data)
            api_keys.append(api_key)
            logging.info(f"Created API key (ID: {api_key.id})")

        # Create credentials
        credentials = []
        for credential_data in seed_data["credentials"]:
            credential = create_credential(session, credential_data)
            credentials.append(credential)
            logging.info(
                f"Created credential for provider: {credential.provider} (ID: {credential.id})"
            )

        # Create assistants
        assistants = []
        for assistant_data in seed_data.get("assistants", []):
            assistant = create_assistant(session, assistant_data)
            assistants.append(assistant)
            logging.info(f"Created assistant: {assistant.name} (ID: {assistant.id})")

        logging.info("Database seeding completed successfully!")
        session.commit()
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
