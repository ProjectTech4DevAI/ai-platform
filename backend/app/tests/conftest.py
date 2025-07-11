from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, text

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.api.deps import get_db
from app.tests.utils.user import authentication_token_from_email
from app.tests.utils.utils import get_superuser_token_headers
from app.seed_data.seed_data import seed_database


def recreate_test_db():
    test_db_name = settings.POSTGRES_DB_TEST
    if test_db_name is None:
        raise ValueError(
            "POSTGRES_DB_TEST is not set but is required for test configuration."
        )
    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        # Disconnect other connections to the test DB
        conn.execute(
            text(
                f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{test_db_name}' AND pid <> pg_backend_pid()
        """
            )
        )
        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
        conn.execute(text(f"CREATE DATABASE {test_db_name}"))


recreate_test_db()
test_engine = create_engine(str(settings.SQLALCHEMY_TEST_DATABASE_URI))


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    with Session(test_engine) as session:
        SQLModel.metadata.create_all(test_engine)
        init_db(session)
        yield session


# Override the get_db dependency to use test session
@pytest.fixture(scope="session", autouse=True)
def override_get_db(db: Session):
    def _get_test_db():
        yield db

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


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
