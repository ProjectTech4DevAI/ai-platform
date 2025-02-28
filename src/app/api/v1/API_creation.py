from typing import Annotated, Any
import logging
import uuid
import hashlib
import os

from fastapi import APIRouter, Depends, Request, HTTPException
from fastcrud.paginated import PaginatedListResponse, compute_offset, paginated_response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from starlette import status 

from ...core.db.database import async_get_db

from ...models import Organization, Project, Credentials
from ...schemas.organization import (
    OrganizationCreateInternal,
    OrganizationRead,
    OrganizationUpdate,
    OrganizationCreate
)
from ...schemas.project import ProjectCreateInternal, ProjectRead, ProjectUpdate, ProjectCreate
from ...schemas.credentials import CredentialsRead

router = APIRouter(tags=["token"])

@router.post("/create_organizations/", response_model=OrganizationRead,status_code=status.HTTP_201_CREATED)
async def create_organization(org: OrganizationCreate, db: AsyncSession = Depends(async_get_db)):
    result = await db.execute(select(Organization).where(Organization.name == org.name))
    existing_org = result.scalars().unique().first()
    
    if existing_org:
        return existing_org  # Return existing organization instead of raising an error
    
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
#    selecting=select(Organization).offset(offset).limit(items_per_page)
    result = await db.execute(select(Organization).offset(offset).limit(items_per_page))
    return result.unique().scalars().all()

@router.post("/project", response_model=ProjectRead, status_code=201)
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
        select(Project).where(
            Project.name == project_name,
            Project.organization_id == org_row.id
        )
    )
    project_row = result.scalars().first()
    
    if project_row:
        return project_row
    
    new_project = Project(name=project_name, organization_id=org_row.id)
    db.add(new_project)
    await db.commit()
    await db.refresh(new_project)
    return new_project

# Get Projects (Async Fix)
@router.get("/projects/", response_model=list[ProjectRead])
async def get_projects(db: AsyncSession = Depends(async_get_db)):
    result = await db.execute(Project.__table__.select())
    return result.scalars().all()

# Authentication Model
@router.post("/authenticate/", response_model=CredentialsRead)
async def authenticate(org_name: str, project_name: str, db: AsyncSession = Depends(async_get_db)):
    # Check if organization exists
    org_result = await db.execute(Organization.__table__.select().where(Organization.name == org_name))
    organization = org_result.scalars().first()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Check if project exists under the organization
    project_result = await db.execute(Project.__table__.select().where(Project.name == project_name, Project.organization_id == organization.id))
    project = project_result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Generate token
    token = str(uuid.uuid4())

    # Create credentials
    new_cred = Credentials(organization_id=organization.id, project_id=project.id, token=token)
    db.add(new_cred)
    await db.commit()
    await db.refresh(new_cred)

    return {"token": token}

    # Verify Token
@router.post("/verify-token/", response_model=CredentialsRead)
async def verify_token(token: str, db: AsyncSession = Depends(async_get_db)):
    # Check if token exists
    token_result = await db.execute(Credentials.__table__.select().where(Credentials.token == token))
    credentials = token_result.scalars().first()
    if not credentials:
        raise HTTPException(status_code=404, detail="Invalid token")
    return credentials
# Revoke Token
@router.post("/revoke-token/", response_model=CredentialsRead)
async def revoke_token(token: str, db: AsyncSession = Depends(async_get_db)):
    # Check if token exists
    token_result = await db.execute(Credentials.__table__.select().where(Credentials.token == token))
    credentials = token_result.scalars().first()
    if not credentials:
        raise HTTPException(status_code=404, detail="Invalid token")
    # Delete the token
    await db.delete(credentials)
    await db.commit()
    return {"token": token}

# Generate API Key
def generate_api_key() -> str:
    return hashlib.sha256(os.urandom(32)).hexdigest()

@router.post("/generate-api-key")
async def generate_and_store_api_key(
    organization_name: OrganizationCreate, project_name: ProjectCreate, db: AsyncSession = Depends(async_get_db)
):
    # Check if the organization exists
    result = await db.execute(select(Organization).where(Organization.name == organization_name.name))
    org = result.scalars().first()
    
    if not org:
        # Create the organization if it doesn't exist
        org = Organization(name=organization_name.name)
        db.add(org)
        await db.commit()
        await db.refresh(org)
    
    # Check if the project exists
    result = await db.execute(
        select(Project).where(
            Project.name == project_name.name, Project.organization_id == org.id
        )
    )
    project = result.scalars().first()
    
    if not project:
        # Create the project if it doesn't exist
        project = Project(name=project_name.name, organization_id=org.id)
        db.add(project)
        await db.commit()
        await db.refresh(project)
    
    # Generate API key
    api_key = generate_api_key()
    
    # Store in creds table
    new_cred = Credentials(organization_id=org.id, project_id=project.id, token=api_key)
    db.add(new_cred)
    await db.commit()
    await db.refresh(new_cred)
    
    return {"api_key": api_key}

