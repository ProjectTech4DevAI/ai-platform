from typing import List, Optional

from pydantic import BaseModel

from .credentials import CredentialsResponse


class ProjectBase(BaseModel):
    name: str
    organization_id: int


class ProjectCreate(ProjectBase):
    pass


class ProjectResponse(ProjectBase):
    id: int
    credentials: Optional[List["CredentialsResponse"]] = []

    class Config:
        orm_mode = True


ProjectResponse.update_forward_refs()
