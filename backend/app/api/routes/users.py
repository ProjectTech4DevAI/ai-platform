import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import func, select

from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.crud import create_user, get_user_by_email, update_user
from app.models import (
    Message,
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.utils import generate_new_account_email, send_email
from app.core.exception_handlers import HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
    include_in_schema=False,
)
def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    logger.info(f"[user.read_all] Fetching users | skip={skip}, limit={limit}")
    count = session.exec(select(func.count()).select_from(User)).one()
    users = session.exec(select(User).offset(skip).limit(limit)).all()
    logger.info(f"[user.read_all] Retrieved {len(users)} users")
    return UsersPublic(data=users, count=count)


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
    include_in_schema=False,
)
def create_user_endpoint(*, session: SessionDep, user_in: UserCreate) -> Any:
    logger.info(f"[user.create] Creating user | email={user_in.email}")
    if get_user_by_email(session=session, email=user_in.email):
        logger.warning(f"[user.create] Email already exists | email={user_in.email}")
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = create_user(session=session, user_create=user_in)

    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
        logger.info(f"[user.create] Account email sent | email={user_in.email}")
    return user


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    logger.info(f"[user.update_me] Updating self | user_id={current_user.id}")
    if user_in.email:
        existing_user = get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            logger.warning(f"[user.update_me] Email conflict | email={user_in.email}")
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    current_user.sqlmodel_update(user_in.model_dump(exclude_unset=True))
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    logger.info(f"[user.update_me] Self update successful | user_id={current_user.id}")
    return current_user


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    logger.info(f"[user.update_password] Password change requested | user_id={current_user.id}")
    if not verify_password(body.current_password, current_user.hashed_password):
        logger.warning(f"[user.update_password] Incorrect current password | user_id={current_user.id}")
        raise HTTPException(status_code=400, detail="Incorrect password")

    if body.current_password == body.new_password:
        logger.warning(f"[user.update_password] New password same as current | user_id={current_user.id}")
        raise HTTPException(
            status_code=400,
            detail="New password cannot be the same as the current one",
        )

    current_user.hashed_password = get_password_hash(body.new_password)
    session.add(current_user)
    session.commit()
    logger.info(f"[user.update_password] Password updated | user_id={current_user.id}")
    return Message(message="Password updated successfully")


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    logger.info(f"[user.read_me] Fetching current user info | user_id={current_user.id}")
    return current_user


@router.delete("/me", response_model=Message)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    logger.info(f"[user.delete_me] Deletion requested | user_id={current_user.id}")
    if current_user.is_superuser:
        logger.warning(f"[user.delete_me] Superuser self-deletion denied | user_id={current_user.id}")
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    session.delete(current_user)
    session.commit()
    logger.info(f"[user.delete_me] User deleted | user_id={current_user.id}")
    return Message(message="User deleted successfully")


@router.post("/signup", response_model=UserPublic)
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    logger.info(f"[user.signup] Registration attempt | email={user_in.email}")
    if get_user_by_email(session=session, email=user_in.email):
        logger.warning(f"[user.signup] Email already exists | email={user_in.email}")
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )

    user_create = UserCreate.model_validate(user_in)
    user = create_user(session=session, user_create=user_create)
    logger.info(f"[user.signup] User registered | user_id={user.id}, email={user.email}")
    return user


@router.get("/{user_id}", response_model=UserPublic, include_in_schema=False)
def read_user_by_id(
    user_id: int, session: SessionDep, current_user: CurrentUser
) -> Any:
    logger.info(f"[user.read_by_id] Fetching user | user_id={user_id}")
    user = session.get(User, user_id)
    if user == current_user:
        logger.info(f"[user.read_by_id] Self request | user_id={user_id}")
        return user

    if not current_user.is_superuser:
        logger.warning(f"[user.read_by_id] Unauthorized access attempt | requested_id={user_id}, user_id={current_user.id}")
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )

    return user


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
    include_in_schema=False,
)
def update_user_endpoint(
    *,
    session: SessionDep,
    user_id: int,
    user_in: UserUpdate,
) -> Any:
    logger.info(f"[user.update] Admin updating user | user_id={user_id}")
    db_user = session.get(User, user_id)
    if not db_user:
        logger.warning(f"[user.update] User not found | user_id={user_id}")
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )

    if user_in.email:
        existing_user = get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            logger.warning(f"[user.update] Email conflict | email={user_in.email}")
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    user = update_user(session=session, db_user=db_user, user_in=user_in)
    logger.info(f"[user.update] User updated | user_id={user_id}")
    return user


@router.delete(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    include_in_schema=False,
)
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: int
) -> Message:
    logger.info(f"[user.delete] Admin deleting user | user_id={user_id}")
    user = session.get(User, user_id)
    if not user:
        logger.warning(f"[user.delete] User not found | user_id={user_id}")
        raise HTTPException(status_code=404, detail="User not found")

    if user == current_user:
        logger.warning(f"[user.delete] Self-deletion denied | user_id={user_id}")
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )

    session.delete(user)
    session.commit()
    logger.info(f"[user.delete] User deleted | user_id={user_id}")
    return Message(message="User deleted successfully")
