import logging
from datetime import timedelta
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core import security
from app.core.config import settings
from app.core.security import get_password_hash
from app.crud import authenticate, get_user_by_email
from app.models import Message, NewPassword, Token, UserPublic
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["login"])


@router.post("/login/access-token")
def login_access_token(
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    token_expiry_minutes: Optional[int] = Form(
        default=settings.ACCESS_TOKEN_EXPIRE_MINUTES, ge=1, le=60 * 24 * 360
    ),
) -> Token:
    """
    OAuth2 compatible token login with customizable expiration time.
    """
    logger.info(
        f"[login.access_token] Login attempt | email={form_data.username}, expiry_minutes={token_expiry_minutes}"
    )

    user = authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        logger.warning(
            f"[login.access_token] Invalid credentials | email={form_data.username}"
        )
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        logger.warning(
            f"[login.access_token] Inactive user login attempt | user_id={user.id}"
        )
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token_expires = timedelta(minutes=token_expiry_minutes)
    logger.info(f"[login.access_token] Login successful | user_id={user.id}")

    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        )
    )


@router.post("/login/test-token", response_model=UserPublic, include_in_schema=False)
def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    logger.info(f"[login.test_token] Token valid | user_id={current_user.id}")
    return current_user


@router.post("/password-recovery/{email}", include_in_schema=False)
def recover_password(email: str, session: SessionDep) -> Message:
    """
    Password Recovery
    """
    logger.info(f"[login.recover_password] Password recovery requested | email={email}")

    user = get_user_by_email(session=session, email=email)
    if not user:
        logger.warning(f"[login.recover_password] Email not found | email={email}")
        raise HTTPException(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )

    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )
    send_email(
        email_to=user.email,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    logger.info(f"[login.recover_password] Recovery email sent | user_id={user.id}")
    return Message(message="Password recovery email sent")


@router.post("/reset-password/", include_in_schema=False)
def reset_password(session: SessionDep, body: NewPassword) -> Message:
    """
    Reset password
    """
    logger.info("[login.reset_password] Password reset requested")

    email = verify_password_reset_token(token=body.token)
    if not email:
        logger.warning("[login.reset_password] Invalid reset token")
        raise HTTPException(status_code=400, detail="Invalid token")

    user = get_user_by_email(session=session, email=email)
    if not user:
        logger.warning(f"[login.reset_password] User not found | email={email}")
        raise HTTPException(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )
    elif not user.is_active:
        logger.warning(f"[login.reset_password] Inactive user | user_id={user.id}")
        raise HTTPException(status_code=400, detail="Inactive user")

    hashed_password = get_password_hash(password=body.new_password)
    user.hashed_password = hashed_password
    session.add(user)
    session.commit()

    logger.info(f"[login.reset_password] Password reset successful | user_id={user.id}")
    return Message(message="Password updated successfully")


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
    include_in_schema=False,
)
def recover_password_html_content(email: str, session: SessionDep) -> Any:
    """
    HTML Content for Password Recovery
    """
    logger.info(
        f"[login.recover_password_html] HTML recovery content requested | email={email}"
    )

    user = get_user_by_email(session=session, email=email)
    if not user:
        logger.warning(f"[login.recover_password_html] Email not found | email={email}")
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )

    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )

    logger.info(
        f"[login.recover_password_html] HTML content generated | user_id={user.id}"
    )
    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )
