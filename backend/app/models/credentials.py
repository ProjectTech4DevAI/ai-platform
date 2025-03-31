from typing import Dict, Any, Optional
import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel

class CredsBase(SQLModel):
    organization_id: int = Field(foreign_key="organization.id")
    is_active: bool = True
    valid: bool = True


class CredsCreate(CredsBase):
    credential: Dict[str, Any] = Field(default=None, sa_column=sa.Column(sa.JSON))  # Change JSON to JSONB


class CredsUpdate(SQLModel):
    credential: Dict[str, Any] | None = Field(default=None, sa_column=sa.Column(sa.JSON))  # Change JSON to JSONB
    is_active: bool | None = Field(default=None)
    valid: bool | None = Field(default=None)


class Creds(CredsBase, table=True):
    id: int = Field(default=None, primary_key=True)
    credential: Dict[str, Any] = Field(default=None, sa_column=sa.Column(sa.JSON))  # Change JSON to JSONB

    # Relationship to Organization model
    organization: Optional["Organization"] = Relationship(back_populates="creds")


class CredsPublic(CredsBase):
    id: int
    credential: Dict[str, Any]
