import random
import string
from uuid import UUID

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.crud.user import get_user_by_email


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


def get_user_id_by_email(db: Session):
    user = get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    return user.id


class SequentialUuidGenerator:
    def __init__(self, start=0):
        self.start = start

    def __iter__(self):
        return self

    def __next__(self):
        uu_id = self.peek()
        self.start += 1
        return uu_id

    def peek(self):
        return UUID(int=self.start)
