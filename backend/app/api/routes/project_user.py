import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session

from app.api.deps import get_db, verify_user_project_organization
from app.crud.project_user import (
    add_user_to_project,
    remove_user_from_project,
    get_users_by_project,
    is_project_admin,
)
from app.models import User, ProjectUserPublic, UserProjectOrg, Message
from app.utils import APIResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/project/users", tags=["project_users"])


@router.post(
    "/{user_id}", response_model=APIResponse[ProjectUserPublic], include_in_schema=False
)
def add_user(
    request: Request,
    user_id: int,
    is_admin: bool = False,
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(verify_user_project_organization),
):
    """
    Add a user to a project.
    """
    project_id = current_user.project_id
    logger.info(
        "[project_user.add_user] Received request to add user | "
        f"user_id={user_id}, project_id={project_id}, added_by={current_user.id}"
    )

    user = session.get(User, user_id)
    if not user:
        logger.warning("[project_user.add_user] User not found | user_id=%s", user_id)
        raise HTTPException(status_code=404, detail="User not found")

    if (
        not current_user.is_superuser
        and not request.headers.get("X-API-KEY")
        and not is_project_admin(session, current_user.id, project_id)
    ):
        logger.warning(
            "[project_user.add_user] Unauthorized attempt to add user | "
            f"user_id={user_id}, project_id={project_id}, attempted_by={current_user.id}"
        )
        raise HTTPException(
            status_code=403, detail="Only project admins or superusers can add users."
        )

    try:
        added_user = add_user_to_project(session, project_id, user_id, is_admin)
        logger.info(
            "[project_user.add_user] User added to project successfully | "
            f"user_id={user_id}, project_id={project_id}"
        )
        return APIResponse.success_response(added_user)
    except ValueError as e:
        logger.warning(
            "[project_user.add_user] Failed to add user to project | "
            f"user_id={user_id}, project_id={project_id}, error={str(e)}"
        )
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/", response_model=APIResponse[list[ProjectUserPublic]], include_in_schema=False
)
def list_project_users(
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(verify_user_project_organization),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    """
    Get all users in a project.
    """
    logger.info(
        "[project_user.list] Listing project users | "
        f"project_id={current_user.project_id}, skip={skip}, limit={limit}"
    )

    users, total_count = get_users_by_project(
        session, current_user.project_id, skip, limit
    )

    logger.info(
        "[project_user.list] Retrieved project users | "
        f"project_id={current_user.project_id}, returned={len(users)}, total_count={total_count}"
    )
    metadata = {"total_count": total_count, "limit": limit, "skip": skip}
    return APIResponse.success_response(data=users, metadata=metadata)


@router.delete(
    "/{user_id}", response_model=APIResponse[Message], include_in_schema=False
)
def remove_user(
    request: Request,
    user_id: int,
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(verify_user_project_organization),
):
    """
    Remove a user from a project.
    """
    project_id = current_user.project_id
    logger.info(
        "[project_user.remove_user] Received request to remove user | "
        f"user_id={user_id}, project_id={project_id}, removed_by={current_user.id}"
    )

    user = session.get(User, user_id)
    if not user:
        logger.warning(
            "[project_user.remove_user] User not found | user_id=%s", user_id
        )
        raise HTTPException(status_code=404, detail="User not found")

    if (
        not current_user.is_superuser
        and not request.headers.get("X-API-KEY")
        and not is_project_admin(session, current_user.id, project_id)
    ):
        logger.warning(
            "[project_user.remove_user] Unauthorized attempt to remove user | "
            f"user_id={user_id}, project_id={project_id}, attempted_by={current_user.id}"
        )
        raise HTTPException(
            status_code=403,
            detail="Only project admins or superusers can remove users.",
        )

    try:
        remove_user_from_project(session, project_id, user_id)
        logger.info(
            "[project_user.remove_user] User removed from project successfully | "
            f"user_id={user_id}, project_id={project_id}"
        )
        return APIResponse.success_response(
            {"message": "User removed from project successfully."}
        )
    except ValueError as e:
        logger.warning(
            "[project_user.remove_user] Failed to remove user | "
            f"user_id={user_id}, project_id={project_id}, error={str(e)}"
        )
        raise HTTPException(status_code=400, detail=str(e))
