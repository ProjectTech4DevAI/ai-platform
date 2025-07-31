import logging
from sqlmodel import Session, select
from datetime import datetime
from app.models import OpenAIThreadCreate, OpenAI_Thread
from app.utils import mask_string

logger = logging.getLogger(__name__)


def upsert_thread_result(session: Session, data: OpenAIThreadCreate):
    statement = select(OpenAI_Thread).where(OpenAI_Thread.thread_id == data.thread_id)
    existing = session.exec(statement).first()

    if existing:
        existing.prompt = data.prompt
        existing.response = data.response
        existing.status = data.status
        existing.error = data.error
        existing.updated_at = datetime.utcnow()
        logger.info(
            f"[upsert_thread_result] Updated existing thread result with ID: {mask_string(data.thread_id)}"
        )
    else:
        new_thread = OpenAI_Thread(**data.dict())
        session.add(new_thread)
        logger.info(
            f"[upsert_thread_result] Created new thread result with ID: {mask_string(new_thread.thread_id)}"
        )
    session.commit()


def get_thread_result(session: Session, thread_id: str) -> OpenAI_Thread | None:
    statement = select(OpenAI_Thread).where(OpenAI_Thread.thread_id == thread_id)
    return session.exec(statement).first()
