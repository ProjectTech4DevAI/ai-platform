from datetime import datetime
from uuid import UUID
from typing import Optional
from sqlmodel import Session, select
from fastapi import HTTPException
from app.core.util import now
from sqlalchemy import cast, String
import json
from app.models import Fine_Tuning, FineTuningJobCreate


def create_fine_tuning_job(
    session: Session,
    request: FineTuningJobCreate,
    split_ratio: float,
    openai_job_id: Optional[str] = None,
    status: Optional[str] = "pending",
    project_id: int = None,
    organization_id: int = None,
) -> Fine_Tuning:
    """Create and store a fine-tuning job in the database."""

    fine_tune_data = request.model_dump(exclude_unset=True)

    base_data = {
        **fine_tune_data,
        "split_ratio": split_ratio,
        "project_id": project_id,
        "organization_id": organization_id,
    }

    if openai_job_id is not None:
        base_data["openai_job_id"] = openai_job_id
    if status is not None:
        base_data["status"] = status

    fine_tune = Fine_Tuning(**base_data)
    fine_tune.updated_at = now()

    session.add(fine_tune)
    session.commit()
    session.refresh(fine_tune)

    return fine_tune


def fetch_by_openai_job_id(session: Session, openai_job_id: str) -> Fine_Tuning:
    job = session.exec(
        select(Fine_Tuning).where(Fine_Tuning.openai_job_id == openai_job_id)
    ).one_or_none()

    if job is None:
        raise HTTPException(status_code=404, detail="OpenAI fine tuning ID not found")

    return job


def fetch_by_id(session: Session, job_id: int) -> Fine_Tuning:
    job = session.get(Fine_Tuning, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def fetch_by_document_id(
    session: Session,
    document_id: UUID,
    split_ratio: float = None,
    base_model: Optional[str] = None,
) -> list[Fine_Tuning]:
    query = select(Fine_Tuning).where(Fine_Tuning.document_id == document_id)

    if split_ratio is not None:
        query = query.where(Fine_Tuning.split_ratio == split_ratio)

    if base_model is not None:
        query = query.where(Fine_Tuning.base_model == base_model)

    jobs = session.exec(query).all()

    return jobs


def update_finetune_status(
    session: Session,
    openai_job_id: str,
    status: str,
    fine_tuned_model: str | None = None,
) -> Fine_Tuning | None:
    job = fetch_by_openai_job_id(session, openai_job_id)
    if not job:
        return None

    job.status = status
    job.fine_tuned_model = fine_tuned_model
    job.updated_at = now()

    session.add(job)
    session.commit()
    session.refresh(job)

    return job
