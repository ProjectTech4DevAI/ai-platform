import pytest
import os

# Set environment before importing ANYTHING else
os.environ["ENVIRONMENT"] = "testing"

from fastapi.testclient import TestClient
from sqlmodel import Session
from sqlalchemy import event
from collections.abc import Generator

# Now import after setting environment
from app.core.config import settings
from app.core.db import engine
from app.api.deps import get_db
from app.main import app
from app.models import APIKeyPublic
from app.tests.utils.user import authentication_token_from_email
from app.tests.utils.utils import get_superuser_token_headers, get_api_key_by_email
from app.seed_data.seed_data import seed_database


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    nested = session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="session", autouse=True)
def seed_baseline():
    """
    Seeds the database with baseline test data including credentials.

    This fixture runs automatically before any tests and ensures:
    - Organizations, users, projects are created
    - OpenAI credentials are created for all test projects
    - Langfuse credentials are created for all test projects
    - All test fixtures can rely on credentials existing
    """
    with Session(engine) as session:
        seed_database(session)  # deterministic baseline with credentials
        yield


@pytest.fixture(scope="function")
def client(db: Session):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="function")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )


@pytest.fixture(scope="function")
def superuser_api_key_header(db: Session) -> dict[str, str]:
    api_key = get_api_key_by_email(db, settings.FIRST_SUPERUSER)
    return {"X-API-KEY": api_key.key}


@pytest.fixture(scope="function")
def user_api_key_header(db: Session) -> dict[str, str]:
    api_key = get_api_key_by_email(db, settings.EMAIL_TEST_USER)
    return {"X-API-KEY": api_key.key}


@pytest.fixture(scope="function")
def superuser_api_key(db: Session) -> APIKeyPublic:
    api_key = get_api_key_by_email(db, settings.FIRST_SUPERUSER)
    return api_key


@pytest.fixture(scope="function")
def user_api_key(db: Session) -> APIKeyPublic:
    """
    Provides an API key for the test user.

    This API key is associated with the Dalgo project, which has both OpenAI
    and Langfuse credentials pre-populated via seed data.
    All tests can assume credentials exist for this user.
    """
    api_key = get_api_key_by_email(db, settings.EMAIL_TEST_USER)
    return api_key
