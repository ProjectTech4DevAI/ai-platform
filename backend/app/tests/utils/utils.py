import random
import string
from uuid import UUID
from typing import Type, TypeVar

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.crud.user import get_user_by_email
from app.crud.api_key import get_api_key_by_value
from app.models import APIKeyPublic, Project, Assistant


T = TypeVar("T")


@pytest.fixture(scope="class")
def openai_credentials():
    settings.OPENAI_API_KEY = "sk-fake123"


def random_lower_string() -> str:
    return "".join(random.choices(string.ascii_lowercase, k=32))


def generate_random_string(length=10):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def random_email() -> str:
    return f"{random_lower_string()}@{random_lower_string()}.com"


def get_superuser_token_headers(client: TestClient) -> dict[str, str]:
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}
    return headers


def get_user_id_by_email(db: Session) -> int:
    user = get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    return user.id


def get_user_from_api_key(db: Session, api_key_headers: dict[str, str]) -> APIKeyPublic:
    key_value = api_key_headers["X-API-KEY"]
    api_key = get_api_key_by_value(db, api_key_value=key_value)
    if api_key is None:
        raise ValueError("Invalid API Key")
    return api_key


def get_non_existent_id(session: Session, model: Type[T]) -> int:
    result = session.exec(select(model.id).order_by(model.id.desc())).first()
    return (result or 0) + 1


def get_project(session: Session, name: str | None = None) -> Project:
    """
    Retrieve an active project from the database.

    If a project name is provided, fetch the active project with that name.
    If no name is provided, fetch any random project.
    """
    if name:
        statement = (
            select(Project).where(Project.name == name, Project.is_active).limit(1)
        )
    else:
        statement = select(Project).where(Project.is_active).limit(1)

    project = session.exec(statement).first()

    if not project:
        raise ValueError("No active projects found")

    return project


def get_assistant(session: Session, name: str | None = None) -> Assistant:
    """
    Retrieve an active assistant from the database.

    If a assistant name is provided, fetch the active assistant with that name.
    If no name is provided, fetch any random assistant.
    """
    if name:
        statement = (
            select(Assistant)
            .where(Assistant.name == name, Assistant.is_deleted == False)
            .limit(1)
        )
    else:
        statement = select(Assistant).where(Assistant.is_deleted == False).limit(1)

    assistant = session.exec(statement).first()

    if not assistant:
        raise ValueError("No active assistants found")

    return assistant


class SequentialUuidGenerator:
    def __init__(self, start=0):
        self.start = start

    def __iter__(self):
        return self

    def __next__(self) -> UUID:
        uu_id = UUID(int=self.start)
        self.start += 1
        return uu_id

    def peek(self) -> UUID:
        return UUID(int=self.start)
