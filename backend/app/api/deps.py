from collections.abc import Generator
from typing import Annotated, Optional

import jwt
from fastapi import Depends, HTTPException, status, Request, Header, Security
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session, select

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.utils import APIResponse
from app.crud.organization import validate_organization
from app.crud.api_key import get_api_key_by_value
from app.models import TokenPayload, User, UserProjectOrg, UserOrganization, ProjectUser, Project, Organization

# reusable_oauth2 = OAuth2PasswordBearer(
#     tokenUrl=f"{settings.API_V1_STR}/login/access-token"
# )


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)
SessionDep = Annotated[Session, Depends(get_db)]
# TokenDep = Annotated[str, Depends(reusable_oauth2)]

def get_current_user(
    session: SessionDep,
    auth_header: str = Security(api_key_header),
) -> UserOrganization:
    """Authenticate user via API Key first, fallback to JWT token."""

    if auth_header.startswith("ApiKey "):
        api_key = auth_header.split(" ", 1)[1]
        api_key_record = get_api_key_by_value(session, api_key)
        if not api_key_record:
            raise HTTPException(status_code=401, detail="Invalid API Key")

        user = session.get(User, api_key_record.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User linked to API Key not found")

        validate_organization(session, api_key_record.organization_id)

        # Return UserOrganization model with organization ID
        return UserOrganization(**user.model_dump(), organization_id=api_key_record.organization_id)

    if auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ", 1)[1]
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
            )
            token_data = TokenPayload(**payload)
        except (InvalidTokenError, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Could not validate credentials",
            )
        user = session.get(User, token_data.sub)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")

        return UserOrganization(**user.model_dump(), organization_id=None)
    raise HTTPException(status_code=401, detail="Invalid Authorization header format")

CurrentUser = Annotated[UserOrganization, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Global handler for HTTPException to return standardized response format.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=APIResponse.failure_response(exc.detail).model_dump() | {"detail": exc.detail},  # TEMPORARY: Keep "detail" for backward compatibility
    )

def verify_user_project_organization(
    db: SessionDep,
    current_user: CurrentUser,
    project_id: int,
    organization_id: int,
) -> UserProjectOrg:
    """
    Verify that the authenticated user is part of the project
    and that the project belongs to the organization.
    """
    if current_user.organization_id and current_user.organization_id != organization_id:
        raise HTTPException(status_code=403, detail="User does not belong to the specified organization")
    
    project_organization = db.exec(
        select(Project, Organization)
        .join(Organization, Project.organization_id == Organization.id)
        .where(Project.id == project_id, Project.is_active==True, Organization.id == organization_id, Organization.is_active==True)
    ).first()

    
    if not project_organization:
        # Determine the exact error based on missing data
        organization = db.exec(select(Organization).where(Organization.id == organization_id)).first()
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        if not organization.is_active:
            raise HTTPException(status_code=400, detail="Organization is not active")  # Use 400 for inactive resources
        
        project = db.exec(select(Project).where(Project.id == project_id)).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        if not project.is_active:
            raise HTTPException(status_code=400, detail="Project is not active")  # Use 400 for inactive resources
        
        raise HTTPException(status_code=403, detail="Project does not belong to the organization")


    current_user.organization_id = organization_id
    
    # Superuser bypasses all checks
    if current_user.is_superuser:
        return UserProjectOrg(**current_user.model_dump(), project_id=project_id)

    # Check if the user is part of the project
    user_in_project = db.exec(
        select(ProjectUser).where(
            ProjectUser.user_id == current_user.id,
            ProjectUser.project_id == project_id,
            ProjectUser.is_deleted == False
        )
    ).first()

    if not user_in_project:
        raise HTTPException(status_code=403, detail="User is not part of the project")

    return UserProjectOrg(**current_user.model_dump(), project_id=project_id)
