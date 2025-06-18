import logging
from typing import Any

from sqlmodel import Session, select

from app.core.security import get_password_hash, verify_password
from app.models import User, UserCreate, UserUpdate

logger = logging.getLogger(__name__)


def create_user(*, session: Session, user_create: UserCreate) -> User:
    logger.info(
        f"[create_user] Starting user creation | {{'email': '{user_create.email}'}}"
    )
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    logger.info(
        f"[create_user] User created successfully | {{'user_id': '{db_obj.id}', 'email': '{db_obj.email}'}}"
    )
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    logger.info(
        f"[update_user] Starting user update | {{'user_id': '{db_user.id}', 'email': '{db_user.email}'}}"
    )
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        logger.info(
            f"[update_user] Updating user password | {{'user_id': '{db_user.id}'}}"
        )
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    logger.info(
        f"[update_user] User updated successfully | {{'user_id': '{db_user.id}', 'email': '{db_user.email}', 'password_updated': {'password' in user_data}}}"
    )
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    logger.info(
        f"[get_user_by_email] Retrieving user by email | {{'email': '{email}'}}"
    )
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    if session_user:
        logger.info(
            f"[get_user_by_email] User retrieved successfully | {{'user_id': '{session_user.id}', 'email': '{email}'}}"
        )
    else:
        logger.warning(
            f"[get_user_by_email] User not found | {{'email': '{email}'}}"
        )
    return session_user


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    logger.info(
        f"[authenticate] Starting user authentication | {{'email': '{email}'}}"
    )
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        logger.warning(
            f"[authenticate] Authentication failed: User not found | {{'email': '{email}'}}"
        )
        return None
    if not verify_password(password, db_user.hashed_password):
        logger.warning(
            f"[authenticate] Authentication failed: Invalid password | {{'user_id': '{db_user.id}', 'email': '{email}'}}"
        )
        return None
    logger.info(
        f"[authenticate] User authenticated successfully | {{'user_id': '{db_user.id}', 'email': '{email}'}}"
    )
    return db_user