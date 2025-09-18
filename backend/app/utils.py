import functools as ft
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Generic, Optional, TypeVar

import jwt
import emails
from jinja2 import Template
from jwt.exceptions import InvalidTokenError
from fastapi import HTTPException
import openai
from openai import OpenAI
from pydantic import BaseModel
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.crud.credentials import get_provider_credential

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def success_response(
        cls, data: T, metadata: Optional[Dict[str, Any]] = None
    ) -> "APIResponse[T]":
        return cls(success=True, data=data, error=None, metadata=metadata)

    @classmethod
    def failure_response(
        cls,
        error: str | list,
        data: Optional[T] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "APIResponse[None]":
        if isinstance(error, list):  # to handle cases when error is a list of errors
            error_message = "\n".join([f"{err['loc']}: {err['msg']}" for err in error])
        else:
            error_message = error

        return cls(success=False, data=data, error=error_message, metadata=metadata)


@dataclass
class EmailData:
    html_content: str
    subject: str


def render_email_template(*, template_name: str, context: dict[str, Any]) -> str:
    template_str = (
        Path(__file__).parent / "email-templates" / "build" / template_name
    ).read_text()
    html_content = Template(template_str).render(context)
    return html_content


def send_email(
    *,
    email_to: str,
    subject: str = "",
    html_content: str = "",
) -> None:
    assert settings.emails_enabled, "no provided configuration for email variables"
    message = emails.Message(
        subject=subject,
        html=html_content,
        mail_from=(settings.EMAILS_FROM_NAME, settings.EMAILS_FROM_EMAIL),
    )
    smtp_options = {"host": settings.SMTP_HOST, "port": settings.SMTP_PORT}
    if settings.SMTP_TLS:
        smtp_options["tls"] = True
    elif settings.SMTP_SSL:
        smtp_options["ssl"] = True
    if settings.SMTP_USER:
        smtp_options["user"] = settings.SMTP_USER
    if settings.SMTP_PASSWORD:
        smtp_options["password"] = settings.SMTP_PASSWORD
    response = message.send(to=email_to, smtp=smtp_options)
    logger.info(f"send email result: {response}")


def generate_test_email(email_to: str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Test email"
    html_content = render_email_template(
        template_name="test_email.html",
        context={"project_name": settings.PROJECT_NAME, "email": email_to},
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_reset_password_email(email_to: str, email: str, token: str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Password recovery for user {email}"
    link = f"{settings.FRONTEND_HOST}/reset-password?token={token}"
    html_content = render_email_template(
        template_name="reset_password.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "username": email,
            "email": email_to,
            "valid_hours": settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS,
            "link": link,
        },
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_new_account_email(
    email_to: str, username: str, password: str
) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - New account for user {username}"
    html_content = render_email_template(
        template_name="new_account.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "username": username,
            "password": password,
            "email": email_to,
            "link": settings.FRONTEND_HOST,
        },
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_password_reset_token(email: str) -> str:
    delta = timedelta(hours=settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS)
    now = datetime.now(timezone.utc)
    expires = now + delta
    exp = expires.timestamp()
    encoded_jwt = jwt.encode(
        {"exp": exp, "nbf": now, "sub": email},
        settings.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )
    return encoded_jwt


def verify_password_reset_token(token: str) -> str | None:
    try:
        decoded_token = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        return str(decoded_token["sub"])
    except InvalidTokenError:
        return None


def mask_string(value: str, mask_char: str = "*") -> str:
    if not value:
        return ""

    length = len(value)
    num_mask = length // 2
    start = (length - num_mask) // 2
    end = start + num_mask

    return value[:start] + (mask_char * num_mask) + value[end:]


def get_openai_client(session: Session, org_id: int, project_id: int) -> OpenAI:
    """
    Fetch OpenAI credentials for the current org/project and return a configured client.
    """
    credentials = get_provider_credential(
        session=session,
        org_id=org_id,
        provider="openai",
        project_id=project_id,
    )

    if not credentials or "api_key" not in credentials:
        logger.error(
            f"[get_openai_client] OpenAI credentials not found. | project_id: {project_id}"
        )
        raise HTTPException(
            status_code=400,
            detail="OpenAI credentials not configured for this organization/project.",
        )

    try:
        return OpenAI(api_key=credentials["api_key"])
    except Exception as e:
        logger.error(
            f"[get_openai_client] Failed to configure OpenAI client. | project_id: {project_id} | error: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to configure OpenAI client: {str(e)}",
        )


def handle_openai_error(e: openai.OpenAIError) -> str:
    if hasattr(e, "body") and isinstance(e.body, dict) and "message" in e.body:
        return e.body["message"]
    elif hasattr(e, "message"):
        return e.message
    elif hasattr(e, "response") and hasattr(e.response, "json"):
        try:
            error_data = e.response.json()
            if isinstance(error_data, dict) and "error" in error_data:
                error_info = error_data["error"]
                if isinstance(error_info, dict) and "message" in error_info:
                    return error_info["message"]
        except:
            pass
    return str(e)


@ft.singledispatch
def load_description(filename: Path) -> str:
    if not filename.exists():
        this = Path(__file__)
        filename = this.parent.joinpath("api", "docs", filename)

    return filename.read_text()


@load_description.register
def _(filename: str) -> str:
    return load_description(Path(filename))
