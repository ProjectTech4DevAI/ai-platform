import uuid

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlmodel import Session

from app.crud import (
    create_organization,
    get_organization_by_name,
    create_project,
    create_user,
    create_api_key,
    get_api_key_by_user_org,
)
from app.models import (
    OrganizationCreate,
    ProjectCreate,
    UserCreate,
    APIKeyPublic,
    Organization,
    Project,
    User,
    APIKey,
)
from app.core.security import get_password_hash
from app.api.deps import (
    SessionDep,
    get_current_active_superuser,
)


router = APIRouter(tags=["onboarding"])


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
    user_id: uuid.UUID
    api_key: str


router = APIRouter(tags=["onboarding"])


class OnboardingRequest(BaseModel):
    organization_name: str
    project_name: str
    email: EmailStr
    password: str
    user_name: str


class OnboardingResponse(BaseModel):
    organization_id: int
    project_id: int
    user_id: uuid.UUID
    api_key: str


@router.post(
    "/onboard",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=OnboardingResponse,
)
def onboard_user(request: OnboardingRequest, session: SessionDep):
    """
    Handles quick onboarding of a new user.
    Accepts organization name, project name, email, password, and user name.
    Returns an API key used for authentication.
    """
    organization = get_organization_by_name(
        session=session, name=request.organization_name
    )
    if not organization:
        org_create = OrganizationCreate(name=request.organization_name)
        organization = create_organization(session=session, org_create=org_create)

    project = (
        session.query(Project).filter(Project.name == request.project_name).first()
    )
    if not project:
        project_create = ProjectCreate(
            name=request.project_name, organization_id=organization.id
        )
        project = create_project(session=session, project_create=project_create)

    user = session.query(User).filter(User.email == request.email).first()
    if not user:
        user_create = UserCreate(
            name=request.user_name,
            email=request.email,
            password=request.password,
        )
        user = create_user(session=session, user_create=user_create)

    existing_key = get_api_key_by_user_org(
        db=session, organization_id=organization.id, user_id=user.id
    )
    if existing_key:
        raise HTTPException(
            status_code=400,
            detail="API key already exists for this user and organization",
        )

    api_key_public = create_api_key(
        session=session, organization_id=organization.id, user_id=user.id
    )

    user.is_superuser = False
    session.add(user)
    session.commit()

    return OnboardingResponse(
        organization_id=organization.id,
        project_id=project.id,
        user_id=user.id,
        api_key=api_key_public.key,
    )
