from datetime import UTC, datetime, timedelta
from typing import Literal

from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db.crud_token_blacklist import crud_token_blacklist
from .schemas import (
    TokenBlacklistCreate,
    ApiKeyData,
)  # ApiKeyData should have fields: organization_name and project_name

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
API_KEY_EXPIRE_MINUTES = settings.API_KEY_EXPIRE_MINUTES  # Configure as needed


async def create_api_key(
    organization_name: str, project_name: str, expires_delta: timedelta | None = None
) -> str:
    """
    Create an API key as a JWT token using the organization and project names.
    """
    payload = {"org": organization_name, "project": project_name}
    if expires_delta:
        expire = datetime.now(UTC).replace(tzinfo=None) + expires_delta
    else:
        expire = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=API_KEY_EXPIRE_MINUTES)
    payload.update({"exp": expire})
    encoded_jwt: str = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def verify_api_key(api_key: str, db: AsyncSession) -> ApiKeyData | None:
    """
    Verify an API key by ensuring it is not blacklisted and decoding its payload.

    Returns an ApiKeyData instance containing the organization and project names
    if the token is valid; otherwise, returns None.
    """
    is_blacklisted = await crud_token_blacklist.exists(db, token=api_key)
    if is_blacklisted:
        return None

    try:
        payload = jwt.decode(api_key, SECRET_KEY, algorithms=[ALGORITHM])
        organization_name = payload.get("org")
        project_name = payload.get("project")
        if organization_name is None or project_name is None:
            return None
        return ApiKeyData(organization_name=organization_name, project_name=project_name)
    except JWTError:
        return None


async def blacklist_api_key(api_key: str, db: AsyncSession) -> None:
    """
    Blacklist an API key so that it can no longer be used.
    """
    payload = jwt.decode(api_key, SECRET_KEY, algorithms=[ALGORITHM])
    expires_at = datetime.fromtimestamp(payload.get("exp"))
    await crud_token_blacklist.create(
        db, object=TokenBlacklistCreate(token=api_key, expires_at=expires_at)
    )
