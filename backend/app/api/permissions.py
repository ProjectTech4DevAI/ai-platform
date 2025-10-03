from enum import Enum
from typing import Annotated
from fastapi import Depends, HTTPException
from sqlmodel import Session

from app.models import UserContext
from app.api.deps import UserContextDep, SessionDep


class Permission(str, Enum):
    """Permission types for authorization checks"""

    SUPERUSER = "require_superuser"
    REQUIRE_ORGANIZATION = "require_organization_id"
    REQUIRE_PROJECT = "require_project_id"


def has_permission(
    user_context: UserContext,
    permission: Permission,
    session: Session | None = None,
) -> bool:
    """
    Check if the user_context has the specified permission.

    Args:
        user_context: The authenticated user context
        permission: The permission to check (Permission enum)
        session: Database session (optional)

    Returns:
        bool: True if user has permission, False otherwise
    """
    match permission:
        case Permission.SUPERUSER:
            return user_context.is_superuser
        case Permission.REQUIRE_ORGANIZATION:
            return user_context.organization_id is not None
        case Permission.REQUIRE_PROJECT:
            return user_context.project_id is not None
        case _:
            return False


def require_permission(permission: Permission):
    """
    Dependency factory for requiring specific permissions in FastAPI routes.

    Usage:
        @app.get("/endpoint", dependencies=[Depends(require_permission(Permission.REQUIRE_ORGANIZATION))])
        def endpoint(user_context: Annotated[UserContext, Depends(get_user_context)]):
            pass
    """

    def permission_checker(
        user_context: UserContextDep,
        session: SessionDep,
    ):
        if not has_permission(user_context, permission, session):
            error_messages = {
                Permission.SUPERUSER: "Insufficient permissions - require superuser access.",
                Permission.REQUIRE_ORGANIZATION: "Insufficient permissions - require organization access.",
                Permission.REQUIRE_PROJECT: "Insufficient permissions - require project access.",
            }
            raise HTTPException(
                status_code=403,
                detail=error_messages.get(permission, "Insufficient permissions"),
            )

    return permission_checker
