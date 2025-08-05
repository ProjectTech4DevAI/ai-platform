import logging
from collections.abc import Generator

import pytest
from dotenv import find_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.models import APIKeyPublic
from app.seed_data.seed_data import seed_database
from app.tests.utils.user import authentication_token_from_email
from app.tests.utils.utils import (
    get_superuser_token_headers,
    get_api_key_by_email,
    load_environment,
)

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session", autouse=True)
def seed_baseline():
    # Load test environment to ensure correct bucket name
    path = find_dotenv(".env.test")
    load_environment(path)

    # Import engine after environment is loaded
    from app.core.db import engine

    with Session(engine) as session:
        logger.info("Seeding baseline data...")
        seed_database(session)  # deterministic baseline
        yield


@pytest.fixture(scope="function", autouse=True)
def cleanup_sessions():
    """Clean up any lingering sessions after each test."""
    yield
    # Force cleanup of any remaining connections in the pool
    from app.core.db import engine

    engine.dispose()


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    from app.core.db import engine

    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()  # Explicitly close the connection


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
    api_key = get_api_key_by_email(db, settings.EMAIL_TEST_USER)
    return api_key
