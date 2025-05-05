from typing import Dict, Any, Optional
import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel
from datetime import datetime

from app.core.util import now

class CredsBase(SQLModel):
    organization_id: int = Field(foreign_key="organization.id")
    is_active: bool = True


class CredsCreate(CredsBase):
    credential: Dict[str, Any] = Field(default=None, sa_column=sa.Column(sa.JSON))


class CredsUpdate(SQLModel):
    credential: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=sa.Column(sa.JSON)
    )
    is_active: Optional[bool] = Field(default=None)


class Credential(CredsBase, table=True):
    id: int = Field(default=None, primary_key=True)
    credential: Dict[str, Any] = Field(default=None, sa_column=sa.Column(sa.JSON))
    inserted_at: datetime = Field(
        default_factory=now,
        sa_column=sa.Column(sa.DateTime, default=datetime.utcnow),
    )
    updated_at: datetime = Field(
        default_factory=now,
        sa_column=sa.Column(sa.DateTime, onupdate=datetime.utcnow),
    )
    deleted_at: Optional[datetime] = Field(
        default=None, sa_column=sa.Column(sa.DateTime, nullable=True)
    )

    organization: Optional["Organization"] = Relationship(back_populates="creds")


class CredsPublic(CredsBase):
    id: int
    credential: Dict[str, Any]
    inserted_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]
