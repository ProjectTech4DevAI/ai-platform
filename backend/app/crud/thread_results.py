from sqlmodel import Session
from datetime import datetime
from app.models import ThreadResponse


def upsert_thread_result(
    session: Session, thread_id: str, question: str, message: str | None
):
    session.merge(
        ThreadResponse(
            thread_id=thread_id,
            question=question,
            message=message,
            updated_at=datetime.utcnow(),
        )
    )
    session.commit()


def get_thread_result(session: Session, thread_id: str) -> ThreadResponse | None:
    return session.get(ThreadResponse, thread_id)
