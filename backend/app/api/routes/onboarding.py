import uuid

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlmodel import Session

from app.crud import create_organization, create_project, create_user, create_api_key
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
from app.api.deps import SessionDep

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


@router.post("/onboard", response_model=OnboardingResponse)
def onboard_user(request: OnboardingRequest, session: SessionDep):
    try:
        existing_organization = (
            session.query(Organization)
            .filter(Organization.name == request.organization_name)
            .first()
        )
        if existing_organization:
            organization = existing_organization
        else:
            org_create = OrganizationCreate(name=request.organization_name)
            organization = create_organization(session=session, org_create=org_create)

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

        existing_user = session.query(User).filter(User.email == request.email).first()
        if existing_user:
            raise HTTPException(
                status_code=400, detail="User already exists with this email"
            )

        user_create = UserCreate(
            name=request.user_name,
            email=request.email,
            password=request.password,
        )
        user = create_user(session=session, user_create=user_create)

        api_key_public = create_api_key(
            session=session, organization_id=organization.id, user_id=user.id
        )

        user.is_superuser = False
        session.add(user)
        session.commit()

        return {
            "organization_id": organization.id,
            "project_id": project.id,
            "user_id": user.id,
            "api_key": api_key_public.key,
        }

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
