from sqlmodel import SQLModel, Field
from typing import Optional


class CasbinRule(SQLModel, table=True):
    __tablename__ = "casbin_rule"

    id: Optional[int] = Field(default=None, primary_key=True)
    ptype: str = Field(
        index=True, max_length=255
    )  # "p" for policy rule, "g" for grouping (role) rule
    # --- v0 to v5 meanings depend on ptype ---
    # For "p" (policy rule):        p, sub, dom, obj, act, eft
    # For "g" (grouping rule):      g, user, role, dom

    v0: Optional[str] = Field(default=None, max_length=255)  # Subject (user or role)
    v1: Optional[str] = Field(default=None, max_length=255)  # Role / Object / Domain
    v2: Optional[str] = Field(default=None, max_length=255)  # Domain / Action
    v3: Optional[str] = Field(
        default=None, max_length=255
    )  # Object (in policy) or unused
    v4: Optional[str] = Field(
        default=None, max_length=255
    )  # Action (in policy) or unused
    v5: Optional[str] = Field(
        default=None, max_length=255
    )  # Effect ("allow"/"deny") or unused
