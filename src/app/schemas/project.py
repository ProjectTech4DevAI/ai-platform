from uuid import UUID
from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel, Field

from .credentials import CredentialsResponse


class ProjectBase(BaseModel):
    name: str = Field(min_length=2, max_length=100, examples=["Example Project"])
    organization_id: int


class ProjectCreate(ProjectBase):
    pass


class ProjectCreateInternal(ProjectBase):
    id: int


class ProjectRead(ProjectBase):
    id: int
    credentials: Optional[List[CredentialsResponse]] = []

    class Config:
        orm_mode = True


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(
        None, min_length=2, max_length=100, examples=["Updated Project Name"]
    )


class ProjectUpdateInternal(ProjectUpdate):
    updated_at: datetime


class ProjectTierUpdate(BaseModel):
    tier_id: Optional[int]


class ProjectDelete(BaseModel):
    is_deleted: bool
    deleted_at: datetime


class ProjectRestoreDeleted(BaseModel):
    is_deleted: bool


ProjectRead.update_forward_refs()
