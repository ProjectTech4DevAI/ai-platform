from typing import Optional
from sqlmodel import SQLModel, Field


class CasbinRule(SQLModel, table=True):
    """
    Represents Casbin policy rules for RBAC.

    Policy type (`ptype`):
    - "p"  -> policy rule (permissions)
    - "g"  -> subject-role assignment (org-level)
    - "g2" -> subject-role assignment (project-level)

    Field meanings based on `ptype`:

    For ptype = "p" (permissions):
        - v0: role
        - v1: resource (e.g., "org_data", "project_data")
        - v2: action (e.g., "read", "write", "delete")

    For ptype = "g" (org-level role assignment):
        - v0: user_id
        - v1: role (e.g., "org_admin", "org_writer", etc.)
        - v2: org_id

    For ptype = "g2" (project-level role assignment):
        - v0: user_id
        - v1: role (e.g., "project_reader", etc.)
        - v2: project_id
    """

    __tablename__ = "casbin_rule"

    id: Optional[int] = Field(default=None, primary_key=True)
    ptype: str = Field(index=True, max_length=255)
    v0: Optional[str] = Field(default=None, max_length=255)
    v1: Optional[str] = Field(default=None, max_length=255)
    v2: Optional[str] = Field(default=None, max_length=255)
    v3: Optional[str] = Field(default=None, max_length=255)
    v4: Optional[str] = Field(default=None, max_length=255)
    v5: Optional[str] = Field(default=None, max_length=255)
