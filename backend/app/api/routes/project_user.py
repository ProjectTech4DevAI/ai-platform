import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import Annotated
from app.api.deps import get_db, verify_user_project_organization
from app.crud.project_user import add_user_to_project, remove_user_from_project, get_users_by_project, is_project_admin
from app.models import User, ProjectUserPublic, UserProjectOrg, Message
from app.utils import APIResponse
 

router = APIRouter(prefix="/project/users", tags=["project_users"])


# Add a user to a project
@router.post("/{user_id}", response_model=APIResponse[ProjectUserPublic])
def add_user(
    user_id: uuid.UUID,
    is_admin: bool = False,
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(verify_user_project_organization)
):
    """
    Add a user to a project.
    """
    project_id = current_user.project_id
    
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Only allow superusers or project admins to add users
    if not current_user.is_superuser and not is_project_admin(session, current_user.id, project_id):
        raise HTTPException(status_code=403, detail="Only project admins or superusers can add users.")
    try:
        added_user = add_user_to_project(session, project_id, user_id, is_admin)
        return APIResponse.success_response(added_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Get all users in a project
@router.get("/", response_model=APIResponse[list[ProjectUserPublic]])
def list_project_users(
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(verify_user_project_organization)
):
    """
    Get all users in a project.
    """
    users = get_users_by_project(session, current_user.project_id)
    return APIResponse.success_response(users)


# Remove a user from a project
@router.delete("/{user_id}", response_model=APIResponse[Message])
def remove_user(
    user_id: uuid.UUID,
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(verify_user_project_organization)
):
    """
    Remove a user from a project.
    """
    # Only allow superusers or project admins to remove user
    project_id = current_user.project_id

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not current_user.is_superuser and not is_project_admin(session, current_user.id, project_id):
        raise HTTPException(status_code=403, detail="Only project admins or superusers can remove users.")
    try:
        remove_user_from_project(session, project_id, user_id)
        return APIResponse.success_response({"message": "User removed from project successfully."})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

