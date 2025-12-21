from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, select

from app.crud.evaluations.cron import (
    process_all_pending_evaluations,
    process_all_pending_evaluations_sync,
)
from app.crud.evaluations.core import create_evaluation_run
from app.core.util import now
from app.models import Organization, Project
from app.models import BatchJob, Organization, Project
from app.tests.utils.test_data import create_test_evaluation_dataset


class TestProcessAllPendingEvaluations:
    """Test processing all pending evaluations across organizations."""

    @pytest.fixture
    def test_dataset(self, db: Session):
        """Create a test dataset."""
        org = db.exec(select(Organization)).first()
        project = db.exec(
            select(Project).where(Project.organization_id == org.id)
        ).first()

        return create_test_evaluation_dataset(
            db=db,
            organization_id=org.id,
            project_id=project.id,
            name="test_dataset_cron",
            description="Test dataset for cron",
            original_items_count=2,
            duplication_factor=1,
        )

    @pytest.mark.asyncio
    async def test_process_all_pending_evaluations_no_orgs(self, db: Session):
        """Test processing when there are no organizations."""
        # This is unlikely in practice but tests the edge case
        # We can't actually remove all orgs due to seed data, so we'll just check
        # that the function handles it gracefully by mocking
        with patch("app.crud.evaluations.cron.select") as mock_select:
            mock_stmt = MagicMock()
            mock_select.return_value = mock_stmt
            db.exec = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))

            result = await process_all_pending_evaluations(session=db)

            assert result["status"] == "success"
            assert result["organizations_processed"] == 0
            assert result["total_processed"] == 0

    @pytest.mark.asyncio
    async def test_process_all_pending_evaluations_no_pending(
        self, db: Session, test_dataset
    ):
        """Test processing when there are no pending evaluations."""
        result = await process_all_pending_evaluations(session=db)

        assert result["status"] == "success"
        assert result["total_processed"] == 0
        assert result["total_failed"] == 0
        assert result["total_still_processing"] == 0

    @pytest.mark.asyncio
    @patch("app.crud.evaluations.cron.poll_all_pending_evaluations")
    async def test_process_all_pending_evaluations_with_results(
        self, mock_poll, db: Session, test_dataset
    ):
        """Test processing with pending evaluations."""
        mock_poll.return_value = {
            "total": 2,
            "processed": 1,
            "failed": 1,
            "still_processing": 0,
            "details": [
                {"run_id": 1, "action": "processed"},
                {"run_id": 2, "action": "failed"},
            ],
        }

        result = await process_all_pending_evaluations(session=db)

        assert result["status"] == "success"
        assert result["organizations_processed"] > 0
        assert result["total_processed"] == 1
        assert result["total_failed"] == 1
        assert result["total_still_processing"] == 0

    @pytest.mark.asyncio
    @patch("app.crud.evaluations.cron.poll_all_pending_evaluations")
    async def test_process_all_pending_evaluations_org_error(
        self, mock_poll, db: Session, test_dataset
    ):
        """Test processing when an organization fails."""
        mock_poll.side_effect = Exception("Org processing failed")

        result = await process_all_pending_evaluations(session=db)

        assert result["status"] == "success"
        assert result["total_failed"] >= 1
        has_error = any("error" in r for r in result["results"])
        assert has_error

    @pytest.mark.asyncio
    async def test_process_all_pending_evaluations_multiple_orgs(
        self, db: Session, test_dataset
    ):
        """Test processing with multiple organizations."""

        new_org = Organization(
            name="Test Org 2",
            inserted_at=now(),
            updated_at=now(),
        )
        db.add(new_org)
        db.commit()
        db.refresh(new_org)

        new_project = Project(
            name="Test Project 2",
            organization_id=new_org.id,
            inserted_at=now(),
            updated_at=now(),
        )
        db.add(new_project)
        db.commit()
        db.refresh(new_project)

        result = await process_all_pending_evaluations(session=db)

        assert result["status"] == "success"
        assert result["organizations_processed"] >= 2

    @pytest.mark.asyncio
    @patch("app.crud.evaluations.cron.poll_all_pending_evaluations")
    async def test_process_all_pending_evaluations_still_processing(
        self, mock_poll, db: Session, test_dataset
    ):
        """Test processing with evaluations still in progress."""
        mock_poll.return_value = {
            "total": 3,
            "processed": 0,
            "failed": 0,
            "still_processing": 3,
            "details": [
                {"run_id": 1, "action": "no_change"},
                {"run_id": 2, "action": "no_change"},
                {"run_id": 3, "action": "no_change"},
            ],
        }

        result = await process_all_pending_evaluations(session=db)

        assert result["status"] == "success"
        assert result["total_still_processing"] == 3
        assert result["total_processed"] == 0
        assert result["total_failed"] == 0

    @pytest.mark.asyncio
    @patch("app.crud.evaluations.cron.poll_all_pending_evaluations")
    async def test_process_all_pending_evaluations_mixed_results(
        self, mock_poll, db: Session, test_dataset
    ):
        """Test processing with mixed results."""
        mock_poll.return_value = {
            "total": 5,
            "processed": 2,
            "failed": 1,
            "still_processing": 2,
            "details": [
                {"run_id": 1, "action": "processed"},
                {"run_id": 2, "action": "processed"},
                {"run_id": 3, "action": "failed"},
                {"run_id": 4, "action": "no_change"},
                {"run_id": 5, "action": "no_change"},
            ],
        }

        result = await process_all_pending_evaluations(session=db)

        assert result["status"] == "success"
        assert result["total_processed"] == 2
        assert result["total_failed"] == 1
        assert result["total_still_processing"] == 2

    @pytest.mark.asyncio
    async def test_process_all_pending_evaluations_fatal_error(self, db: Session):
        """Test handling of fatal errors."""
        with patch("app.crud.evaluations.cron.select") as mock_select:
            mock_select.side_effect = Exception("Database connection lost")

            result = await process_all_pending_evaluations(session=db)

            assert result["status"] == "error"
            assert "error" in result
            assert result["total_processed"] == 0


class TestProcessAllPendingEvaluationsSync:
    """Test synchronous wrapper for processing."""

    @pytest.fixture
    def test_dataset(self, db: Session):
        """Create a test dataset."""
        org = db.exec(select(Organization)).first()
        project = db.exec(
            select(Project).where(Project.organization_id == org.id)
        ).first()

        return create_test_evaluation_dataset(
            db=db,
            organization_id=org.id,
            project_id=project.id,
            name="test_dataset_sync",
            description="Test dataset for sync",
            original_items_count=2,
            duplication_factor=1,
        )

    def test_process_all_pending_evaluations_sync(self, db: Session, test_dataset):
        """Test synchronous wrapper."""
        result = process_all_pending_evaluations_sync(session=db)

        assert result["status"] == "success"
        assert "organizations_processed" in result
        assert "total_processed" in result
        assert "total_failed" in result
        assert "total_still_processing" in result

    @patch("app.crud.evaluations.cron.process_all_pending_evaluations")
    def test_process_all_pending_evaluations_sync_calls_async(
        self, mock_async, db: Session, test_dataset
    ):
        """Test that sync wrapper calls async function."""
        mock_async.return_value = {
            "status": "success",
            "organizations_processed": 1,
            "total_processed": 0,
            "total_failed": 0,
            "total_still_processing": 0,
            "results": [],
        }

        with patch("asyncio.run") as mock_run:
            mock_run.return_value = mock_async.return_value
            result = process_all_pending_evaluations_sync(session=db)

            mock_run.assert_called_once()
            assert result["status"] == "success"


class TestCronIntegration:
    """Integration tests for cron functionality."""

    @pytest.fixture
    def test_dataset(self, db: Session):
        """Create a test dataset."""
        org = db.exec(select(Organization)).first()
        project = db.exec(
            select(Project).where(Project.organization_id == org.id)
        ).first()

        return create_test_evaluation_dataset(
            db=db,
            organization_id=org.id,
            project_id=project.id,
            name="test_dataset_integration",
            description="Test dataset for integration",
            original_items_count=2,
            duplication_factor=1,
        )

    @pytest.mark.asyncio
    @patch("app.utils.get_openai_client")
    @patch("app.utils.get_langfuse_client")
    @patch("app.crud.evaluations.processing.get_batch_job")
    @patch("app.crud.batch_operations.poll_batch_status")
    async def test_cron_with_pending_evaluation(
        self,
        mock_poll_status,
        mock_get_batch,
        mock_langfuse_client,
        mock_openai_client,
        db: Session,
        test_dataset,
    ):
        """Test cron processing with a pending evaluation."""
        batch_job = BatchJob(
            provider="openai",
            provider_batch_id="batch_cron_test",
            provider_status="in_progress",
            job_type="evaluation",
            total_items=2,
            status="submitted",
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
            inserted_at=now(),
            updated_at=now(),
        )
        db.add(batch_job)
        db.commit()
        db.refresh(batch_job)

        eval_run = create_evaluation_run(
            session=db,
            run_name="test_cron_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )
        eval_run.batch_job_id = batch_job.id
        eval_run.status = "processing"
        db.add(eval_run)
        db.commit()
        db.refresh(eval_run)

        mock_openai_client.return_value = MagicMock()
        mock_langfuse_client.return_value = MagicMock()
        mock_get_batch.return_value = batch_job

        result = await process_all_pending_evaluations(session=db)

        assert result["status"] == "success"
        assert result["organizations_processed"] >= 1

    @pytest.mark.asyncio
    async def test_cron_handles_completed_evaluations(self, db: Session, test_dataset):
        """Test that cron doesn't process already completed evaluations."""
        eval_run = create_evaluation_run(
            session=db,
            run_name="test_completed_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )
        eval_run.status = "completed"
        db.add(eval_run)
        db.commit()

        result = await process_all_pending_evaluations(session=db)

        assert result["status"] == "success"
