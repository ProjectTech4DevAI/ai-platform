"""
Tests for the LLM job service functions.
"""
import pytest
from unittest.mock import patch, MagicMock

from fastapi import HTTPException
from sqlmodel import Session

from app.crud import JobCrud
from app.models import JobStatus, JobType
from app.models.llm import (
    LLMCallRequest,
    CompletionConfig,
    QueryParams,
    LLMCallResponse,
    Usage,
)
from app.models.llm.request import LLMCallConfig
from app.services.llm.jobs import start_job, handle_job_error, execute_job
from app.tests.utils.utils import get_project



class TestStartJob:
    """Test cases for the start_job function."""

    @pytest.fixture
    def llm_call_request(self):
        
        return LLMCallRequest(
            query=QueryParams(input="Test query"),
            config=LLMCallConfig(
                completion=CompletionConfig(
                    provider="openai",
                    params={"model": "gpt-4"},
                )
            ),
        )

    def test_start_job_success(self, db: Session, llm_call_request: LLMCallRequest):
        """Test successful job creation and Celery task scheduling."""

        request = llm_call_request
        project = get_project(db)

        with patch("app.services.llm.jobs.start_high_priority_job") as mock_schedule:
            mock_schedule.return_value = "fake-task-id-123"

            job_id = start_job(db, request, project.id, project.organization_id)

            job_crud = JobCrud(session=db)
            job = job_crud.get(job_id)
            assert job is not None
            assert job.job_type == JobType.LLM_API
            assert job.status == JobStatus.PENDING
            assert job.trace_id is not None

            mock_schedule.assert_called_once()
            _, kwargs = mock_schedule.call_args
            assert kwargs["function_path"] == "app.services.llm.jobs.execute_job"
            assert kwargs["project_id"] == project.id
            assert kwargs["organization_id"] == project.organization_id
            assert kwargs["job_id"] == str(job_id)
            assert "request_data" in kwargs


    def test_start_job_celery_scheduling_fails(self, db: Session, llm_call_request: LLMCallRequest):
        """Test start_job when Celery task scheduling fails."""
        project = get_project(db)

        with patch("app.services.llm.jobs.start_high_priority_job") as mock_schedule:
            mock_schedule.side_effect = Exception("Celery connection failed")

            with pytest.raises(HTTPException) as exc_info:
                start_job(db, llm_call_request, project.id, project.organization_id)

            assert exc_info.value.status_code == 500
            assert "Internal server error while executing LLM call" in str(
                exc_info.value.detail
            )


    def test_start_job_exception_during_job_creation(self, db: Session, llm_call_request: LLMCallRequest):
        """Test handling of exceptions during job creation in database."""
        project = get_project(db)

        with patch("app.services.llm.jobs.JobCrud") as mock_job_crud:
            mock_crud_instance = MagicMock()
            mock_crud_instance.create.side_effect = Exception(
                "Database connection failed"
            )
            mock_job_crud.return_value = mock_crud_instance

            with pytest.raises(Exception) as exc_info:
                start_job(db, llm_call_request, project.id, project.organization_id)

            assert "Database connection failed" in str(exc_info.value)


class TestHandleJobError:
    """Test cases for the handle_job_error function."""

    def test_handle_job_error(self, db: Session):
        """Test handle_job_error successfully sends callback and updates job status."""
        job_crud = JobCrud(session=db)
        job = job_crud.create(job_type=JobType.LLM_API, trace_id="test-trace")
        db.commit()

        callback_url = "https://example.com/callback"
        error_message = "Test error occurred"

        with patch("app.services.llm.jobs.Session") as mock_session_class, \
             patch("app.services.llm.jobs.send_callback") as mock_send_callback:
            mock_session_class.return_value.__enter__.return_value = db
            mock_session_class.return_value.__exit__.return_value = None

            result = handle_job_error(
                job_id=job.id,
                callback_url=callback_url,
                error=error_message
            )

            mock_send_callback.assert_called_once()
            call_args = mock_send_callback.call_args
            assert call_args[1]["callback_url"] == callback_url

            callback_data = call_args[1]["data"]
            assert callback_data["success"] is False
            assert callback_data["error"] == error_message
            assert callback_data["data"] is None

            db.refresh(job)
            assert job.status == JobStatus.FAILED
            assert job.error_message == error_message

            assert result["success"] is False
            assert result["error"] == error_message
            assert result["data"] is None


    def test_handle_job_error_without_callback_url(self, db: Session):
        """Test handle_job_error updates job when no callback URL provided."""
        job_crud = JobCrud(session=db)
        job = job_crud.create(job_type=JobType.LLM_API, trace_id="test-trace")
        db.commit()

        error_message = "Another test error"

        with patch("app.services.llm.jobs.Session") as mock_session_class, \
             patch("app.services.llm.jobs.send_callback") as mock_send_callback:
            mock_session_class.return_value.__enter__.return_value = db
            mock_session_class.return_value.__exit__.return_value = None

            result = handle_job_error(
                job_id=job.id,
                callback_url=None,
                error=error_message
            )

            mock_send_callback.assert_not_called()

            db.refresh(job)
            assert job.status == JobStatus.FAILED
            assert job.error_message == error_message

            # Verify return value structure
            assert result["success"] is False
            assert result["error"] == error_message


    def test_handle_job_error_callback_failure_still_updates_job(self, db: Session):
        """Test that job is updated even if callback sending fails."""
        job_crud = JobCrud(session=db)
        job = job_crud.create(job_type=JobType.LLM_API, trace_id="test-trace")
        db.commit()

        callback_url = "https://example.com/callback"
        error_message = "Test error with callback failure"

        with patch("app.services.llm.jobs.Session") as mock_session_class, \
             patch("app.services.llm.jobs.send_callback") as mock_send_callback:
            mock_session_class.return_value.__enter__.return_value = db
            mock_session_class.return_value.__exit__.return_value = None

            mock_send_callback.side_effect = Exception("Callback service unavailable")

            with pytest.raises(Exception) as exc_info:
                handle_job_error(
                    job_id=job.id,
                    callback_url=callback_url,
                    error=error_message
                )

            assert "Callback service unavailable" in str(exc_info.value)


class TestExecuteJob:
    """Test suite for execute_job."""

    @pytest.fixture
    def job_for_execution(self, db: Session):
        job = JobCrud(session=db).create(job_type=JobType.LLM_API, trace_id="test-trace")
        db.commit()
        return job

    @pytest.fixture
    def request_data(self):
        return {
            "query": {"input": "Test query"},
            "config": {"completion": {"provider": "openai", "params": {"model": "gpt-4"}}},
            "include_provider_response": False,
            "callback_url": None,
        }

    @pytest.fixture
    def mock_llm_response(self):
        return LLMCallResponse(
            id="resp-123",
            output="Test response",
            model="gpt-4",
            provider="openai",
            usage=Usage(input_tokens=10, output_tokens=20, total_tokens=30),
            llm_response=None,
        )
    
    @pytest.fixture
    def job_env(self, db, mock_llm_response):
        """Set up common environment with patched Session, provider, and callback."""
        with (
            patch("app.services.llm.jobs.Session") as mock_session_class,
            patch("app.services.llm.jobs.get_llm_provider") as mock_get_provider,
            patch("app.services.llm.jobs.send_callback") as mock_send_callback,
        ):
            mock_session_class.return_value.__enter__.return_value = db
            mock_session_class.return_value.__exit__.return_value = None

            # Mock LLM provider
            mock_provider = MagicMock()
            mock_get_provider.return_value = mock_provider

            # Provide everything needed to tests
            yield {
                "session": mock_session_class,
                "get_provider": mock_get_provider,
                "provider": mock_provider,
                "send_callback": mock_send_callback,
                "mock_llm_response": mock_llm_response,
            }

    def _execute_job(self, job, db, request_data):
        project = get_project(db)
        return execute_job(
            request_data=request_data,
            project_id=project.id,
            organization_id=project.organization_id,
            job_id=str(job.id),
            task_id="task-123",
            task_instance=None,
        )

    def test_success_with_callback(self, db, job_env, job_for_execution, request_data):
        """Successful execution with callback."""
        env = job_env
        request_data["callback_url"] = "https://example.com/callback"

        env["provider"].execute.return_value = (env["mock_llm_response"], None)
        result = self._execute_job(job_for_execution, db, request_data)

        env["get_provider"].assert_called_once()
        env["send_callback"].assert_called_once()
        assert result["success"]
        db.refresh(job_for_execution)
        assert job_for_execution.status == JobStatus.SUCCESS

    def test_success_without_callback(self, db, job_env, job_for_execution, request_data):
        """Successful execution without callback."""
        env = job_env
        env["provider"].execute.return_value = (env["mock_llm_response"], None)

        result = self._execute_job(job_for_execution, db, request_data)

        env["send_callback"].assert_not_called()
        assert result["success"]
        db.refresh(job_for_execution)
        assert job_for_execution.status == JobStatus.SUCCESS

    def test_provider_returns_error(self, db, job_env, job_for_execution, request_data):
        """Provider returns error (no callback)."""
        env = job_env
        env["provider"].execute.return_value = (None, "API rate limit exceeded")

        result = self._execute_job(job_for_execution, db, request_data)

        assert not result["success"]
        assert "rate limit" in result["error"]
        db.refresh(job_for_execution)
        assert job_for_execution.status == JobStatus.FAILED

    def test_provider_error_with_callback(self, db, job_env, job_for_execution, request_data):
        """Provider returns error (with callback)."""
        env = job_env
        request_data["callback_url"] = "https://example.com/callback"
        env["provider"].execute.return_value = (None, "Invalid API key")

        result = self._execute_job(job_for_execution, db, request_data)

        env["send_callback"].assert_called_once()
        assert not result["success"]

    def test_exception_during_execution(self, db, job_env, job_for_execution, request_data):
        """Unhandled exception in provider execution."""
        env = job_env
        env["provider"].execute.side_effect = Exception("Network timeout")

        result = self._execute_job(job_for_execution, db, request_data)

        assert not result["success"]
        assert "Network timeout" in result["error"]

    def test_exception_during_provider_retrieval(self, db, job_env, job_for_execution, request_data):
        """Provider not configured exception."""
        env = job_env
        env["get_provider"].side_effect = Exception("Provider not configured")

        result = self._execute_job(job_for_execution, db, request_data)

        assert not result["success"]
        assert "Provider not configured" in result["error"]
