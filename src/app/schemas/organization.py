from uuid import UUID
from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel, Field

from .project import ProjectRead
from .credentials import CredentialsRead


class OrganizationBase(BaseModel):
    name: str = Field(min_length=2, max_length=100, examples=["Example Organization"])


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationCreateInternal(OrganizationBase):
    id: int


class OrganizationRead(OrganizationBase):
    id: int
    projects: Optional[List[ProjectRead]] = []
    credentials: Optional[List[CredentialsRead]] = []

    class Config:
        orm_mode = True


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(
        None, min_length=2, max_length=100, examples=["Updated Organization Name"]
    )


class OrganizationUpdateInternal(OrganizationUpdate):
    updated_at: datetime


class OrganizationTierUpdate(BaseModel):
    tier_id: Optional[int]


class OrganizationDelete(BaseModel):
    is_deleted: bool
    deleted_at: datetime


class OrganizationRestoreDeleted(BaseModel):
    is_deleted: bool


OrganizationRead.model_rebuild()
