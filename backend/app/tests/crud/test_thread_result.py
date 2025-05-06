import pytest
from sqlmodel import SQLModel, Session, create_engine

from app.models import ThreadResponse
from app.crud import upsert_thread_result, get_thread_result


@pytest.fixture
def session():
    """Creates a new in-memory database session for each test."""
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_upsert_and_get_thread_result(session: Session):
    thread_id = "thread_test_123"
    question = "What is the capital of Spain?"
    message = "Madrid is the capital of Spain."

    # Initially insert
    upsert_thread_result(session, thread_id, question, message)

    # Retrieve
    result = get_thread_result(session, thread_id)

    assert result is not None
    assert result.thread_id == thread_id
    assert result.question == question
    assert result.message == message

    # Update with new message
    updated_message = "Madrid."
    upsert_thread_result(session, thread_id, question, updated_message)

    result_updated = get_thread_result(session, thread_id)
    assert result_updated.message == updated_message
