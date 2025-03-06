from uuid import UUID
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel

from ..models import Credentials, Organization, Project
from ..core.db.database import async_get_db
from ..core.logger import logging
from ..schemas.credentials import CredentialsRead

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="Authorization", auto_error=True)


class APIKeyResponse(BaseModel):
    organization_id: int
    organization_name: str
    project_id: int
    project_name: str
    api_key: str


async def get_current_org(
    token: str = Security(api_key_header),
    db: AsyncSession = Depends(async_get_db),
) -> APIKeyResponse:
    try:
        valid_token = UUID(token, version=4)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid API key format : {token}")
    # Query credentials table
    token_result = await db.execute(select(Credentials).where(Credentials.token == valid_token))
    credentials = token_result.scalars().first()

    if not credentials:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Fetch associated organization and project
    org_result = await db.execute(
        select(Organization).where(Organization.id == credentials.organization_id)
    )
    organization = org_result.scalars().first()

    proj_result = await db.execute(select(Project).where(Project.id == credentials.project_id))
    project = proj_result.scalars().first()

    if not organization or not project:
        raise HTTPException(status_code=401, detail="Invalid API key association")

    return APIKeyResponse(
        organization_id=credentials.organization_id,
        organization_name=organization.name,
        project_id=credentials.project_id,
        project_name=project.name,
        api_key=str(credentials.token),
    )
