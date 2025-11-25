import logging
from fastapi import HTTPException
from sqlmodel import Session

from app.core.security import encrypt_credentials, get_password_hash
from app.crud import (
    api_key_manager,
    get_organization_by_name,
    get_project_by_name,
    get_user_by_email,
)
from app.core.providers import validate_provider, validate_provider_credentials
from app.models import (
    APIKey,
    Credential,
    OnboardingRequest,
    OnboardingResponse,
    Organization,
    OrganizationCreate,
    Project,
    ProjectCreate,
    User,
    UserCreate,
)

logger = logging.getLogger(__name__)


def onboard_project(
    session: Session, onboard_in: OnboardingRequest
) -> OnboardingResponse:
    """
    Create or link resources for onboarding.

    - Organization:
    - Create new if `organization_name` does not exist.
    - Otherwise, attach project to existing organization.

    - Project:
    - Create if `project_name` does not exist in org.
    - If already exists, return 409 Conflict.

    - User:
    - Create and link if `email` does not exist.
    - If exists, attach to project.

    - OpenAI API Key (optional):
    - If provided, encrypted and stored as project credentials.
    - If omitted, project is created without OpenAI credentials.
    """
    existing_organization = get_organization_by_name(
        session=session, name=onboard_in.organization_name
    )
    if existing_organization:
        organization = existing_organization
    else:
        org_create = OrganizationCreate(name=onboard_in.organization_name)
        organization = Organization.model_validate(org_create)
        session.add(organization)
        session.flush()

    project = get_project_by_name(
        session=session,
        project_name=onboard_in.project_name,
        organization_id=organization.id,
    )
    if project:
        raise HTTPException(
            status_code=409,
            detail=f"Project already exists for organization '{organization.name}'",
        )

    project_create = ProjectCreate(
        name=onboard_in.project_name, organization_id=organization.id
    )
    project = Project.model_validate(project_create)
    session.add(project)
    session.flush()

    user = get_user_by_email(session=session, email=onboard_in.email)
    if not user:
        user_create = UserCreate(
            email=onboard_in.email,
            full_name=onboard_in.user_name,
            password=onboard_in.password,
        )
        user = User.model_validate(
            user_create,
            update={"hashed_password": get_password_hash(user_create.password)},
        )
        session.add(user)
        session.flush()

    raw_key, key_prefix, key_hash = api_key_manager.generate()

    api_key = APIKey(
        key_prefix=key_prefix,
        key_hash=key_hash,
        user_id=user.id,
        organization_id=project.organization_id,
        project_id=project.id,
    )

    session.add(api_key)

    created_credentials: list[Credential] = []

    if onboard_in.credential:
        for item in onboard_in.credential:
            provider_str, values = next(iter(item.items()))

            encrypted_credentials = encrypt_credentials(values)

            cred_row = Credential(
                organization_id=organization.id,
                project_id=project.id,
                is_active=True,
                provider=provider_str,
                credential=encrypted_credentials,
            )
            session.add(cred_row)

            created_credentials.append(cred_row)
    session.commit()
    logger.info(
        "[onboard_project] Onboarding completed successfully. "
        f"org_id={organization.id}, project_id={project.id}, user_id={user.id}"
    )

    return OnboardingResponse(
        organization_id=organization.id,
        organization_name=organization.name,
        project_id=project.id,
        project_name=project.name,
        user_id=user.id,
        user_email=user.email,
        api_key=raw_key,
    )
