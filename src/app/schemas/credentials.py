from typing import Dict, Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, EmailStr


class CredentialsBase(BaseModel):
    organization_id: int
    project_id: int
    secrets: Dict[str, str]
    email: str = Field(examples=["user@example.com"])


class CredentialsCreate(CredentialsBase):
    pass


class CredentialsCreateInternal(CredentialsBase):
    id: int
    token: UUID
    created_at: datetime


class CredentialsRead(CredentialsBase):
    id: int
    token: UUID
    created_at: datetime

    class Config:
        orm_mode = True


class CredentialsUpdate(BaseModel):
    secrets: Optional[Dict[str, str]] = None
    email: Optional[EmailStr] = Field(None, examples=["updated@example.com"])


class CredentialsUpdateInternal(CredentialsUpdate):
    updated_at: datetime


class CredentialsDelete(BaseModel):
    is_deleted: bool
    deleted_at: datetime


class CredentialsRestoreDeleted(BaseModel):
    is_deleted: bool


CredentialsRead.model_rebuild()
