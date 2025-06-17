import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr

from app.crud import (
    create_organization,
    get_organization_by_name,
    create_project,
    create_user,
    create_api_key,
    get_api_key_by_project_user,
)
from app.models import (
    OrganizationCreate,
    ProjectCreate,
    UserCreate,
    Project,
    User,
    APIKey,
)
from app.api.deps import (
    SessionDep,
    get_current_active_superuser,
)

router = APIRouter(tags=["onboarding"])
logger = logging.getLogger(__name__)


# Pydantic models for input validation
class OnboardingRequest(BaseModel):
    organization_name: str
    project_name: str
    email: EmailStr
    password: str
    user_name: str


class OnboardingResponse(BaseModel):
    organization_id: int
    project_id: int
    user_id: int
    api_key: str


@router.post(
    "/onboard",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=OnboardingResponse,
)
def onboard_user(request: OnboardingRequest, session: SessionDep):
    """
    Handles quick onboarding of a new user: Accepts Organization name, project name, email, password, and user name, then gives back an API key which
    will be further used for authentication.
    """
    logger.info(f"[onboarding.start] Onboarding started for email={request.email}")

    # Validate organization
    existing_organization = get_organization_by_name(
        session=session, name=request.organization_name
    )
    if existing_organization:
        organization = existing_organization
        logger.info(f"[onboarding.organization] Using existing organization | id={organization.id}, name={organization.name}")
    else:
        org_create = OrganizationCreate(name=request.organization_name)
        organization = create_organization(session=session, org_create=org_create)
        logger.info(f"[onboarding.organization] Created new organization | id={organization.id}, name={organization.name}")

    # Validate project
    existing_project = (
        session.query(Project).filter(Project.name == request.project_name).first()
    )
    if existing_project:
        project = existing_project
        logger.info(f"[onboarding.project] Using existing project | id={project.id}, name={project.name}")
    else:
        project_create = ProjectCreate(
            name=request.project_name, organization_id=organization.id
        )
        project = create_project(session=session, project_create=project_create)
        logger.info(f"[onboarding.project] Created new project | id={project.id}, name={project.name}")

    # Validate user
    existing_user = session.query(User).filter(User.email == request.email).first()
    if existing_user:
        user = existing_user
        logger.info(f"[onboarding.user] Using existing user | id={user.id}, email={user.email}")
    else:
        user_create = UserCreate(
            name=request.user_name,
            email=request.email,
            password=request.password,
        )
        user = create_user(session=session, user_create=user_create)
        logger.info(f"[onboarding.user] Created new user | id={user.id}, email={user.email}")

    # Check if API key already exists
    existing_key = get_api_key_by_project_user(
        session=session, user_id=user.id, project_id=project.id
    )
    if existing_key:
        logger.warning(f"[onboarding.apikey] API key already exists for user={user.id}, project={project.id}")
        raise HTTPException(
            status_code=400,
            detail="API key already exists for this user and project.",
        )

    # Create API key
    api_key_public = create_api_key(
        session=session,
        organization_id=organization.id,
        user_id=user.id,
        project_id=project.id,
    )
    logger.info(f"[onboarding.apikey] API key created | key_id={api_key_public.id}, user_id={user.id}, project_id={project.id}")

    # Set user as non-superuser and save to session
    user.is_superuser = False
    session.add(user)
    session.commit()

    logger.info(f"[onboarding.success] Onboarding completed | org_id={organization.id}, project_id={project.id}, user_id={user.id}")
    return OnboardingResponse(
        organization_id=organization.id,
        project_id=project.id,
        user_id=user.id,
        api_key=api_key_public.key,
    )
