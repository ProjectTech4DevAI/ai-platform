from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.models import (
    APIKey,
    Assistant,
    Organization,
    Project,
    ProjectUser,
    User,
    OpenAI_Thread,
    OpenAI_Conversation,
    Credential,
    Collection,
)
from app.tests.utils.user import authentication_token_from_email
from app.tests.utils.utils import get_superuser_token_headers
from app.seed_data.seed_data import seed_database


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        init_db(session)
        yield session
        # Delete data in reverse dependency order
        session.execute(delete(ProjectUser))  # Many-to-many relationship
        session.execute(delete(Assistant))
        session.execute(delete(OpenAI_Conversation))
        session.execute(delete(Credential))
        session.execute(delete(Project))
        session.execute(delete(Organization))
        session.execute(delete(APIKey))
        session.execute(delete(User))
        session.execute(delete(OpenAI_Thread))
        session.execute(delete(Collection))
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )


@pytest.fixture(scope="session", autouse=True)
def load_seed_data(db):
    seed_database(db)
    yield
