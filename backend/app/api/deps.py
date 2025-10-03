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
from app.models import (
    TokenPayload,
    User,
    UserProjectOrg,
    UserOrganization,
    Project,
    Organization,
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
        api_key_record = get_api_key_by_value(session, api_key)
        if not api_key_record:
            raise HTTPException(status_code=401, detail="Invalid API Key")

        user = session.get(User, api_key_record.user_id)
        if not user:
            raise HTTPException(
                status_code=404, detail="User linked to API Key not found"
            )

        return user  # Return only User object

    if token:
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
        api_key_record = get_api_key_by_value(session, api_key)
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
        api_key_record = get_api_key_by_value(session, api_key)
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
