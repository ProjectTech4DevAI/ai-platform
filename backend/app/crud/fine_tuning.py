from datetime import datetime
from uuid import UUID
import logging
from typing import Optional
from sqlmodel import Session, select
from fastapi import HTTPException
from app.core.util import now
from sqlalchemy import cast, String
import json
from app.models import Fine_Tuning, FineTuningJobCreate, FineTuningUpdate

logger = logging.getLogger(__name__)


def create_fine_tuning_job(
    session: Session,
    request: FineTuningJobCreate,
    split_ratio: float,
    openai_job_id: Optional[str] = None,
    status: Optional[str] = "pending",
    project_id: int = None,
    organization_id: int = None,
) -> Fine_Tuning:
    existing_jobs = fetch_by_document_id(
        session=session,
        document_id=request.document_id,
        split_ratio=split_ratio,
        base_model=request.base_model,
        project_id=project_id,
    )

    if existing_jobs:
        job = existing_jobs[0]
        if job.openai_job_id:
            logger.warning(
                f"fine-tune job with OpenAI ID already exists: job_id={job.id}, "
                f"document_id={request.document_id}, split_ratio={split_ratio}, base_model={request.base_model}, "
                f"project_id={project_id}"
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Fine-tuning job already exists for document={request.document_id}, "
                    f"split_ratio={split_ratio}, base_model={request.base_model}"
                ),
            )
        logger.info(
            f"Reusing existing fine-tune job ID={job.id}, project_id={project_id}"
        )
        return job

    fine_tune_data = request.model_dump(exclude_unset=True)
    base_data = {
        **fine_tune_data,
        "split_ratio": split_ratio,
        "project_id": project_id,
        "organization_id": organization_id,
        "status": status,
    }

    if openai_job_id is not None:
        base_data["openai_job_id"] = openai_job_id

    fine_tune = Fine_Tuning(**base_data)
    fine_tune.updated_at = now()

    session.add(fine_tune)
    session.commit()
    session.refresh(fine_tune)

    logger.info(
        f"Created new fine-tuning job ID={fine_tune.id}, project_id={project_id}"
    )
    return fine_tune


def fetch_by_openai_job_id(
    session: Session, openai_job_id: str, project_id: int
) -> Fine_Tuning:
    job = session.exec(
        select(Fine_Tuning).where(
            Fine_Tuning.openai_job_id == openai_job_id,
            Fine_Tuning.project_id == project_id,
        )
    ).one_or_none()

    if job is None:
        logger.warning(
            f"Fine-tune job not found for openai_job_id={openai_job_id}, project_id={project_id}"
        )
        raise HTTPException(status_code=404, detail="OpenAI fine tuning ID not found")

    return job


def fetch_by_id(session: Session, job_id: int, project_id: int) -> Fine_Tuning:
    logger.debug(f"Fetching fine-tune job by job_id={job_id}, project_id={project_id}")
    job = session.exec(
        select(Fine_Tuning).where(
            Fine_Tuning.id == job_id, Fine_Tuning.project_id == project_id
        )
    ).one_or_none()

    if job is None:
        logger.warning(
            f"Fine-tune job not found: job_id={job_id}, project_id={project_id}"
        )
        raise HTTPException(status_code=404, detail="Job not found")

    logger.info(f"Fetched fine-tune job ID={job.id}, project_id={project_id}")
    return job


def fetch_by_document_id(
    session: Session,
    document_id: UUID,
    project_id: int,
    split_ratio: float = None,
    base_model: Optional[str] = None,
) -> list[Fine_Tuning]:
    query = select(Fine_Tuning).where(
        Fine_Tuning.document_id == document_id, Fine_Tuning.project_id == project_id
    )

    if split_ratio is not None:
        query = query.where(Fine_Tuning.split_ratio == split_ratio)
    if base_model is not None:
        query = query.where(Fine_Tuning.base_model == base_model)

    jobs = session.exec(query).all()
    logger.info(
        f"Found {len(jobs)} fine-tune jobs for document_id={document_id}, project_id={project_id}"
    )
    return jobs


def update_finetune_job(
    session: Session,
    job: Fine_Tuning,
    update: FineTuningUpdate,
) -> Fine_Tuning:
    for key, value in update.dict(exclude_unset=True).items():
        setattr(job, key, value)

    job.updated_at = now()

    session.add(job)
    session.commit()
    session.refresh(job)

    logger.info(f"Updated fine-tune job ID={job.id}, project_id={job.project_id}")
    return job
