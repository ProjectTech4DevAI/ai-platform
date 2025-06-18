import logging
from sqlmodel import Session, select
from datetime import datetime
from app.models import OpenAIThreadCreate, OpenAI_Thread

logger = logging.getLogger(__name__)


def upsert_thread_result(session: Session, data: OpenAIThreadCreate):
    logger.info(
        f"[upsert_thread_result] Starting thread upsert | {{'thread_id': '{data.thread_id}'}}"
    )
    statement = select(OpenAI_Thread).where(OpenAI_Thread.thread_id == data.thread_id)
    existing = session.exec(statement).first()

    if existing:
        logger.info(
            f"[upsert_thread_result] Updating existing thread | {{'thread_id': '{data.thread_id}'}}"
        )
        existing.prompt = data.prompt
        existing.response = data.response
        existing.status = data.status
        existing.error = data.error
        existing.updated_at = datetime.utcnow()
        operation = "updated"
    else:
        logger.info(
            f"[upsert_thread_result] Creating new thread | {{'thread_id': '{data.thread_id}'}}"
        )
        new_thread = OpenAI_Thread(**data.dict())
        session.add(new_thread)
        operation = "created"

    session.commit()
    logger.info(
        f"[upsert_thread_result] Thread {operation} successfully | {{'thread_id': '{data.thread_id}', 'status': '{data.status}'}}"
    )


def get_thread_result(session: Session, thread_id: str) -> OpenAI_Thread | None:
    logger.info(
        f"[get_thread_result] Retrieving thread | {{'thread_id': '{thread_id}'}}"
    )
    statement = select(OpenAI_Thread).where(OpenAI_Thread.thread_id == thread_id)
    thread = session.exec(statement).first()
    if thread:
        logger.info(
            f"[get_thread_result] Thread retrieved successfully | {{'thread_id': '{thread_id}', 'status': '{thread.status}'}}"
        )
    else:
        logger.warning(
            f"[get_thread_result] Thread not found | {{'thread_id': '{thread_id}'}}"
        )
    return thread
