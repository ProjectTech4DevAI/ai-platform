from typing import Dict
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel


class CredentialsBase(BaseModel):
    organization_id: int
    project_id: int
    secrets: Dict[str, str]
    email: str


class CredentialsCreate(CredentialsBase):
    pass


class CredentialsResponse(CredentialsBase):
    id: int
    token: UUID
    creation: datetime

    class Config:
        orm_mode = True
