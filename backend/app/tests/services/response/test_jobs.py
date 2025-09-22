import pytest
from unittest.mock import patch
from sqlmodel import Session
from app.services.response.jobs import start_job
from app.models import ResponsesAPIRequest, JobType, JobStatus
from app.crud import JobCrud
from app.tests.utils.utils import get_project


def test_start_job(db: Session):
    request = ResponsesAPIRequest(
        assistant_id="assistant_123",
        question="What is the capital of France?",
    )

    project = get_project(db)
    # Patch Celery scheduling
    with patch("app.services.response.jobs.start_high_priority_job") as mock_schedule:
        mock_schedule.return_value = "fake-task-id"

        job_id = start_job(db, request, project.id, project.organization_id)

        job_crud = JobCrud(session=db)
        job = job_crud.get(job_id)
        assert job is not None
        assert job.job_type == JobType.RESPONSE
        assert job.status == JobStatus.PENDING
        assert job.trace_id is not None

        # Validate Celery was called correctly
        mock_schedule.assert_called_once()
        _, kwargs = mock_schedule.call_args
        assert kwargs["function_path"] == "app.services.response.jobs.execute_job"
        assert kwargs["project_id"] == project.id
        assert kwargs["organization_id"] == project.organization_id
        assert kwargs["job_id"] == str(job_id)
        assert kwargs["request_data"]["assistant_id"] == "assistant_123"
