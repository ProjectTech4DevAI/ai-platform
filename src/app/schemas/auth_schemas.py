from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict

# Organization Schema
class OrganizationBase(BaseModel):
    name: str

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationResponse(OrganizationBase):
    id: UUID

    class Config:
        orm_mode = True

# Project Schema
class ProjectBase(BaseModel):
    name: str
    organization_id: UUID

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase):
    id: UUID

    class Config:
        orm_mode = True

# Credentials Schema
class CredentialsBase(BaseModel):
    organization_id: UUID
    project_id: UUID
    secrets: Dict[str, str]

class CredentialsCreate(CredentialsBase):
    pass

class CredentialsResponse(CredentialsBase):
    id: UUID
    token: UUID
    creation: datetime

    class Config:
        orm_mode = True

class TokenResponse(BaseModel):
    token: UUID
