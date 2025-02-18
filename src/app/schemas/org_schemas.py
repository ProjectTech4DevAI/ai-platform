from uuid import UUID
from typing import List, Optional

from pydantic import BaseModel

from .project_schemas import ProjectResponse
from .cred_schemas import CredentialsResponse


class OrganizationBase(BaseModel):
    name: str


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationResponse(OrganizationBase):
    id: UUID
    projects: Optional[List["ProjectResponse"]] = []
    credentials: Optional[List["CredentialsResponse"]] = []

    class Config:
        orm_mode = True


OrganizationResponse.update_forward_refs()
