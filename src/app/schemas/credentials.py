from typing import Dict
from uuid import UUID
from datetime import datetime

from sqlmodel import SQLModel
from pydantic import EmailStr, Field


class CredentialsBase(SQLModel):
    organization_id: int
    project_id: int
    secrets: Dict[str, str] | None = {}
    email: EmailStr | None = Field(None, examples=["updated@example.com"])


class CredentialsCreate(CredentialsBase):
    pass


class CredentialsRead(CredentialsBase):
    id: int
    token: UUID
    created_at: datetime
    updated_at: datetime | None = None


class CredentialsUpdate(SQLModel):
    secrets: Dict[str, str] | None = None
    email: EmailStr | None = Field(None, examples=["updated@example.com"])


class CredentialsDelete(SQLModel):
    is_deleted: bool
    deleted_at: datetime


class CredentialsRestoreDeleted(SQLModel):
    is_deleted: bool
