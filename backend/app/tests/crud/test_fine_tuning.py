import pytest
from sqlmodel import Session
from fastapi import HTTPException

from app.models import FineTuningUpdate, FineTuningJobCreate
from app.crud import (
    create_fine_tuning_job,
    fetch_by_openai_job_id,
    fetch_by_id,
    fetch_by_document_id,
    update_finetune_job,
)
from app.tests.utils.test_data import create_test_fine_tuning_jobs
from app.tests.utils.utils import get_project, get_document


def test_create_fine_tuning_job(db: Session):
    project = get_project(db, "Dalgo")
    document = get_document(db)

    job_request = FineTuningJobCreate(
        document_id=document.id,
        base_model="gpt-4",
        split_ratio=[0.8, 0.2],
    )

    created_job = create_fine_tuning_job(
        session=db,
        request=job_request,
        split_ratio=0.8,
        project_id=project.id,
        organization_id=project.organization_id,
    )

    assert created_job.id is not None
    assert created_job.document_id == document.id
    assert created_job.split_ratio == 0.8
    assert created_job.project_id == project.id
    assert created_job.openai_job_id is None


def test_create_fine_tuning_job_duplicate_openai_id_raises(db: Session):
    jobs, project = create_test_fine_tuning_jobs(db, ratios=[0.3, 0.4])
    job = jobs[0]

    with pytest.raises(HTTPException) as exc:
        create_fine_tuning_job(
            session=db,
            request=job,
            split_ratio=job.split_ratio,
            project_id=project.id,
            organization_id=project.organization_id,
        )
    assert exc.value.status_code == 400
    assert "already exists" in exc.value.detail


def test_fetch_by_openai_job_id_success(db: Session):
    jobs, project = create_test_fine_tuning_jobs(db, ratios=[0.3])
    job = jobs[0]

    result = fetch_by_openai_job_id(
        db, openai_job_id=job.openai_job_id, project_id=project.id
    )
    assert result.id == job.id


def test_fetch_by_openai_job_id_not_found(db: Session):
    with pytest.raises(HTTPException) as exc:
        fetch_by_openai_job_id(db, "invalid_id", project_id=999)
    assert exc.value.status_code == 404


def test_fetch_by_id_success(db: Session):
    jobs, project = create_test_fine_tuning_jobs(db, ratios=[0.3, 0.4])
    job = jobs[0]

    result = fetch_by_id(db, job_id=job.id, project_id=project.id)
    assert result.id == job.id


def test_fetch_by_id_not_found(db: Session):
    with pytest.raises(HTTPException) as exc:
        fetch_by_id(db, job_id=9999, project_id=1)
    assert exc.value.status_code == 404


def test_fetch_by_document_id_filters(db: Session):
    jobs, project = create_test_fine_tuning_jobs(db, ratios=[0.3, 0.4])
    job = jobs[0]

    results = fetch_by_document_id(
        session=db,
        document_id=job.document_id,
        project_id=project.id,
        split_ratio=job.split_ratio,
        base_model=job.base_model,
    )
    assert len(results) == 1
    assert results[0].id == job.id


def test_update_finetune_job(db: Session):
    jobs, _ = create_test_fine_tuning_jobs(db, ratios=[0.3, 0.4])
    job = jobs[0]

    update = FineTuningUpdate(status="completed", fine_tuned_model="ft:gpt-4:custom")
    updated_job = update_finetune_job(db, job=job, update=update)

    assert updated_job.status == "completed"
    assert updated_job.fine_tuned_model == "ft:gpt-4:custom"
