from uuid import UUID
from typing import List, Optional

from pydantic import BaseModel

from .project import ProjectResponse
from .credentials import CredentialsResponse


class OrganizationBase(BaseModel):
    name: str


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationResponse(OrganizationBase):
    id: int
    projects: Optional[List["ProjectResponse"]] = []
    credentials: Optional[List["CredentialsResponse"]] = []

    class Config:
        orm_mode = True


OrganizationResponse.update_forward_refs()
