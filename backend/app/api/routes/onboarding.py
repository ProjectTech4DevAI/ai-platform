import re
import secrets

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, model_validator, field_validator
from sqlmodel import Session

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


# Pydantic models for input validation
class OnboardingRequest(BaseModel):
    organization_name: str
    project_name: str
    email: EmailStr | None = None
    password: str | None = None
    user_name: str | None = None

    @staticmethod
    def _clean_username(raw: str, max_len: int = 200) -> str:
        """
        Normalize a string into a safe username that can also be used
        as the local part of an email address.
        """
        username = re.sub(r"[^A-Za-z0-9._]", "_", raw.strip().lower())
        username = re.sub(r"[._]{2,}", "_", username)  # collapse repeats
        username = username.strip("._")  # remove leading/trailing
        return username[:max_len]

    @model_validator(mode="after")
    def set_defaults(self):
        if self.user_name is None:
            self.user_name = self.project_name + " User"

        if self.email is None:
            local_part = self._clean_username(self.user_name, max_len=200)
            suffix = secrets.token_hex(3)
            self.email = f"{local_part}.{suffix}@kaapi.org"

        if self.password is None:
            self.password = secrets.token_urlsafe(12)
        return self


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
    # Validate organization
    existing_organization = get_organization_by_name(
        session=session, name=request.organization_name
    )
    if existing_organization:
        organization = existing_organization
    else:
        org_create = OrganizationCreate(name=request.organization_name)
        organization = create_organization(session=session, org_create=org_create)

    # Validate project
    existing_project = (
        session.query(Project).filter(Project.name == request.project_name).first()
    )
    if existing_project:
        project = existing_project  # Use the existing project
    else:
        project_create = ProjectCreate(
            name=request.project_name, organization_id=organization.id
        )
        project = create_project(session=session, project_create=project_create)

    # Validate user
    existing_user = session.query(User).filter(User.email == request.email).first()
    if existing_user:
        user = existing_user
    else:
        user_create = UserCreate(
            full_name=request.user_name,
            email=request.email,
            password=request.password,
        )
        user = create_user(session=session, user_create=user_create)

    # Check if API key exists for the user and project
    existing_key = get_api_key_by_project_user(
        session=session, user_id=user.id, project_id=project.id
    )
    if existing_key:
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

    # Set user as non-superuser and save to session
    user.is_superuser = False
    session.add(user)
    session.commit()

    return OnboardingResponse(
        organization_id=organization.id,
        project_id=project.id,
        user_id=user.id,
        api_key=api_key_public.key,
    )
