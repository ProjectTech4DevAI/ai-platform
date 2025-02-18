from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from .credentials import CredentialsResponse


class ProjectBase(BaseModel):
    name: str
    organization_id: UUID


class ProjectCreate(ProjectBase):
    pass


class ProjectResponse(ProjectBase):
    id: UUID
    credentials: Optional[List["CredentialsResponse"]] = []

    class Config:
        orm_mode = True


ProjectResponse.update_forward_refs()
