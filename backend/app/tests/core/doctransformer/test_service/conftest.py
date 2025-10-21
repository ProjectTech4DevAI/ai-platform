"""
Pytest fixtures for document transformation service tests.
"""
import os
from typing import Any, Callable, Generator, Tuple
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session
from tenacity import retry, stop_after_attempt, wait_fixed

from app.crud import get_project_by_id
from app.models import User
from app.core.config import settings
from app.models import Document, Project, UserProjectOrg
from app.tests.utils.document import DocumentStore
from app.tests.utils.auth import TestAuthContext


@pytest.fixture(scope="class")
def aws_credentials() -> None:
    """Set up AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = settings.AWS_DEFAULT_REGION


@pytest.fixture
def fast_execute_job() -> Generator[Callable[[int, UUID, str, str], Any], None, None]:
    """Create a version of execute_job without retry delays for faster testing."""
    from app.core.doctransform import service

    original_execute_job = service.execute_job

    @retry(
        stop=stop_after_attempt(2), wait=wait_fixed(0.01)
    )  # Very fast retry for tests
    def fast_execute_job_func(
        project_id: int, job_id: UUID, transformer_name: str, target_format: str
    ) -> Any:
        # Call the original function's implementation without the decorator
        return original_execute_job.__wrapped__(
            project_id, job_id, transformer_name, target_format
        )

    with patch.object(service, "execute_job", fast_execute_job_func):
        yield fast_execute_job_func


@pytest.fixture
def current_user(db: Session, user_api_key: TestAuthContext) -> UserProjectOrg:
    """Create a test user for testing."""
    api_key = user_api_key
    user = api_key.user
    return UserProjectOrg(
        **user.model_dump(),
        project_id=api_key.project_id,
        organization_id=api_key.organization_id
    )


@pytest.fixture
def background_tasks() -> BackgroundTasks:
    """Create BackgroundTasks instance."""
    return BackgroundTasks()


@pytest.fixture
def test_document(
    db: Session, current_user: UserProjectOrg
) -> Tuple[Document, Project]:
    """Create a test document for the current user's project."""
    store = DocumentStore(db, current_user.project_id)
    project = get_project_by_id(session=db, project_id=current_user.project_id)
    return store.put(), project
