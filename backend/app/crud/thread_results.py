from sqlmodel import Session, select
from datetime import datetime
from app.models import OpenAIThreadCreate, OpenAI_Thread


def upsert_thread_result(session: Session, data: OpenAIThreadCreate):
    statement = select(OpenAI_Thread).where(OpenAI_Thread.thread_id == data.thread_id)
    existing = session.exec(statement).first()

    if existing:
        existing.prompt = data.prompt
        existing.response = data.response
        existing.status = data.status
        existing.error = data.error
        existing.updated_at = datetime.utcnow()
    else:
        new_thread = OpenAI_Thread(**data.dict())
        session.add(new_thread)

    session.commit()


def get_thread_result(session: Session, thread_id: str) -> OpenAI_Thread | None:
    statement = select(OpenAI_Thread).where(OpenAI_Thread.thread_id == thread_id)
    return session.exec(statement).first()
