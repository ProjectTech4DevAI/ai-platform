from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session, select

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.core.security import api_key_manager
from app.crud.organization import validate_organization
from app.models import (
    AuthContext,
    TokenPayload,
    User,
    UserOrganization,
    UserProjectOrg,
)


reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token", auto_error=False
)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)
SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_user(
    session: SessionDep,
    token: TokenDep,
    api_key: Annotated[str, Depends(api_key_header)],
) -> User:
    """Authenticate user via API Key first, fallback to JWT token. Returns only User."""

    if api_key:
        api_key_record = api_key_manager.verify(session, api_key)
        if not api_key_record:
            raise HTTPException(status_code=401, detail="Invalid API Key")

        user = session.get(User, api_key_record.user_id)
        if not user:
            raise HTTPException(
                status_code=404, detail="User linked to API Key not found"
            )

        return user  # Return only User object

    elif token:
        try:
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

        return user  # Return only User object

    raise HTTPException(status_code=401, detail="Invalid Authorization format")


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_user_org(
    current_user: CurrentUser, session: SessionDep, request: Request
) -> UserOrganization:
    """Extend `User` with organization_id if available, otherwise return UserOrganization without it."""

    organization_id = None
    api_key = request.headers.get("X-API-KEY")
    if api_key:
        api_key_record = api_key_manager.verify(session, api_key)
        if api_key_record:
            validate_organization(session, api_key_record.organization_id)
            organization_id = api_key_record.organization_id

    return UserOrganization(
        **current_user.model_dump(), organization_id=organization_id
    )


CurrentUserOrg = Annotated[UserOrganization, Depends(get_current_user_org)]


def get_current_user_org_project(
    current_user: CurrentUser, session: SessionDep, request: Request
) -> UserProjectOrg:
    api_key = request.headers.get("X-API-KEY")
    organization_id = None
    project_id = None

    if api_key:
        api_key_record = api_key_manager.verify(session, api_key)
        if api_key_record:
            validate_organization(session, api_key_record.organization_id)
            organization_id = api_key_record.organization_id
            project_id = api_key_record.project_id

    else:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    return UserProjectOrg(
        **current_user.model_dump(),
        organization_id=organization_id,
        project_id=project_id,
    )


CurrentUserOrgProject = Annotated[UserProjectOrg, Depends(get_current_user_org_project)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


def get_current_active_superuser_org(current_user: CurrentUserOrg) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


def get_auth_context(
    session: SessionDep,
    token: TokenDep,
    api_key: Annotated[str, Depends(api_key_header)],
) -> AuthContext:
    """
    Verify valid authentication (API Key or JWT token) and return authenticated user context.
    Returns AuthContext with user info, project_id, and organization_id.
    Authorization logic should be handled in routes.
    """
    if api_key:
        auth_context = api_key_manager.verify(session, api_key)
        if not auth_context:
            raise HTTPException(status_code=401, detail="Invalid API Key")

        if not auth_context.user.is_active:
            raise HTTPException(status_code=403, detail="Inactive user")

        if not auth_context.organization.is_active:
            raise HTTPException(status_code=403, detail="Inactive Organization")

        if not auth_context.project.is_active:
            raise HTTPException(status_code=403, detail="Inactive Project")

        return auth_context

    elif token:
        try:
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
            raise HTTPException(status_code=403, detail="Inactive user")

        auth_context = AuthContext(
            user_id=user.id,
            user=user,
        )
        return auth_context

    else:
        raise HTTPException(status_code=401, detail="Invalid Authorization format")


AuthContextDep = Annotated[AuthContext, Depends(get_auth_context)]
