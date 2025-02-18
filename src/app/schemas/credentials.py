from typing import Dict
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel


class CredentialsBase(BaseModel):
    organization_id: UUID
    project_id: UUID
    secrets: Dict[str, str]
    email: str


class CredentialsCreate(CredentialsBase):
    pass


class CredentialsResponse(CredentialsBase):
    id: UUID
    token: UUID
    creation: datetime

    class Config:
        orm_mode = True
