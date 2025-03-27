from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

class CredsBase(SQLModel):
    is_active: bool = True
    valid: bool = True


class CredsCreate(CredsBase):
    openai_api_key: str 


class CredsUpdate(SQLModel):
    openai_api_key: str | None = Field(default=None)  
    is_active: bool | None = Field(default=None)
    valid: bool | None = Field(default=None)


class Creds(CredsBase, table=True):
    id: int = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organization.id")  
    openai_api_key: str 


class CredsPublic(CredsBase):
    id: int
    organization_id: int
    openai_api_key: str  
