import random
import string
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from typing import Type, TypeVar

from app.core.config import settings
from app.crud.user import get_user_by_email
from app.models import Organization, Project, APIKey
from app.crud import create_api_key, get_api_key_by_value
from uuid import uuid4


T = TypeVar("T")


@pytest.fixture(scope="class")
def openai_credentials():
    settings.OPENAI_API_KEY = "sk-fake123"


def random_lower_string() -> str:
    return "".join(random.choices(string.ascii_lowercase, k=32))


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


def get_real_api_key_headers(db: Session) -> dict[str, str]:
    owner_id = get_user_id_by_email(db)

    # Step 1: Create real organization and project
    organization = Organization(name=f"Test Org {uuid4()}")
    db.add(organization)
    db.commit()
    db.refresh(organization)

    project = Project(name=f"Test Project {uuid4()}", organization_id=organization.id)
    db.add(project)
    db.commit()
    db.refresh(project)

    # Step 2: Create API key
    api_key = create_api_key(
        db,
        organization_id=organization.id,
        user_id=owner_id,
        project_id=project.id,
    )

    return {"X-API-Key": api_key.key}


def get_user_from_api_key(db: Session, api_key_headers: dict[str, str]) -> int:
    key_value = api_key_headers["X-API-Key"]
    api_key = get_api_key_by_value(db, api_key_value=key_value)
    return api_key


def get_non_existent_id(session: Session, model: Type[T]) -> int:
    result = session.exec(select(model.id).order_by(model.id.desc())).first()
    return (result or 0) + 1


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
