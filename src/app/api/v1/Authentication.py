import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, Request, HTTPException
from fastcrud.paginated import PaginatedListResponse, compute_offset, paginated_response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from starlette import status
from pydantic import BaseModel

from ...core.db.database import async_get_db

from ...models import Organization, Project, Credentials
from ...schemas.organization import (
    OrganizationCreateInternal,
    OrganizationRead,
    OrganizationUpdate,
    OrganizationCreate,
)
from ...schemas.project import ProjectCreateInternal, ProjectRead, ProjectUpdate, ProjectCreate
from ...schemas.credentials import CredentialsRead


class APIKeyRequest(BaseModel):
    organization_name: str
    project_name: str


router = APIRouter(tags=["token"])


@router.post("/create_organizations/", response_model=OrganizationRead)
async def create_organization(org: OrganizationCreate, db: AsyncSession = Depends(async_get_db)):
    result = await db.execute(select(Organization).where(Organization.name == org.name))
    existing_org = result.scalars().first()

    if existing_org:
        return existing_org

    new_org = Organization(**org.dict())
    db.add(new_org)
    await db.commit()
    await db.refresh(new_org)
    return new_org


@router.get("/organizations/", response_model=list[OrganizationRead])
async def list_organizations(
    db: AsyncSession = Depends(async_get_db), page: int = 1, items_per_page: int = 10
):
    offset = (page - 1) * items_per_page
    result = await db.execute(select(Organization).offset(offset).limit(items_per_page))
    return result.unique().scalars().all()


@router.post("/create_project", response_model=ProjectRead)
async def create_project(
    organization_name: str,
    project_name: str,
    db: AsyncSession = Depends(async_get_db),
):
    result = await db.execute(select(Organization).where(Organization.name == organization_name))
    org_row = result.scalars().first()

    if not org_row:
        raise HTTPException(status_code=404, detail="Organization not found")

    result = await db.execute(
        select(Project).where(Project.name == project_name, Project.organization_id == org_row.id)
    )
    project_row = result.scalars().first()

    if project_row:
        return project_row

    new_project = Project(name=project_name, organization_id=org_row.id)
    db.add(new_project)
    await db.commit()
    await db.refresh(new_project)
    return new_project


@router.get("/projects/", response_model=list[ProjectRead])
async def list_projects(
    db: AsyncSession = Depends(async_get_db), page: int = 1, items_per_page: int = 10
):
    offset = (page - 1) * items_per_page
    result = await db.execute(select(Project).offset(offset).limit(items_per_page))
    return result.unique().scalars().all()


def generate_api_key() -> str:
    return str(uuid.uuid4())


@router.post("/generate-api-key")
async def generate_and_store_api_key(
    request: APIKeyRequest,
    db: AsyncSession = Depends(async_get_db),
) -> dict:
    organization_name = request.organization_name
    project_name = request.project_name

    result = await db.execute(select(Organization).where(Organization.name == organization_name))
    org = result.scalars().first()

    if not org:
        org = Organization(name=organization_name.name)
        db.add(org)
        await db.commit()
        await db.refresh(org)

    result = await db.execute(
        select(Project).where(Project.name == project_name, Project.organization_id == org.id)
    )
    project = result.unique().scalars().first()

    if not project:
        project = Project(name=project_name, organization_id=org.id)
        db.add(project)
        await db.commit()
        await db.refresh(project)

    api_key = generate_api_key()

    new_cred = Credentials(
        organization_id=org.id,
        project_id=project.id,
        email="default@example.com",
        secrets={"keys": "value"},
        token=api_key,
    )
    db.add(new_cred)
    await db.commit()
    await db.refresh(new_cred)

    return {"api_key": api_key}


@router.post("/verify-api-key/", response_model=CredentialsRead)
async def verify_api_key(token: str, db: AsyncSession = Depends(async_get_db)):
    try:
        valid_token = UUID(token, version=4)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid token format")

    # Query the database for the token
    token_result = await db.execute(select(Credentials).where(Credentials.token == valid_token))
    credentials = token_result.scalars().first()

    if not credentials:
        raise HTTPException(status_code=404, detail="Invalid token")

    return credentials


@router.post("/revoke-api-key/", response_model=CredentialsRead)
async def revoke_api_key(token: str, db: AsyncSession = Depends(async_get_db)):
    token_result = await db.execute(select(Credentials).where(Credentials.token == token))
    credentials = token_result.scalars().first()
    if not credentials:
        raise HTTPException(status_code=404, detail="Invalid token")
    await db.delete(credentials)
    await db.commit()
    return {"token": token}
