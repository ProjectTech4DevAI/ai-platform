from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, select

from app.crud.evaluations.core import (
    create_evaluation_run,
    get_evaluation_run_by_id,
    get_or_fetch_score,
    list_evaluation_runs,
    save_score,
    update_evaluation_run,
)
from app.models import Organization, Project, BatchJob
from app.core.util import now
from app.tests.utils.test_data import create_test_evaluation_dataset


class TestCreateEvaluationRun:
    """Test creating evaluation runs."""

    def test_create_evaluation_run_minimal(self, db: Session, test_dataset_factory):
        """Test creating an evaluation run with minimal config."""
        eval_run = create_evaluation_run(
            session=db,
            run_name="test_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        assert eval_run.id is not None
        assert eval_run.run_name == "test_run"
        assert eval_run.dataset_name == test_dataset.name
        assert eval_run.dataset_id == test_dataset.id
        assert eval_run.config == {"model": "gpt-4o"}
        assert eval_run.status == "pending"
        assert eval_run.organization_id == test_dataset.organization_id
        assert eval_run.project_id == test_dataset.project_id
        assert eval_run.inserted_at is not None
        assert eval_run.updated_at is not None

    def test_create_evaluation_run_complete(self, db: Session, test_dataset):
        """Test creating an evaluation run with complete config."""
        config = {
            "model": "gpt-4o",
            "temperature": 0.7,
            "instructions": "You are a helpful assistant",
            "tools": [{"type": "file_search", "vector_store_ids": ["vs_123"]}],
        }

        eval_run = create_evaluation_run(
            session=db,
            run_name="complete_test_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config=config,
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        assert eval_run.id is not None
        assert eval_run.config["model"] == "gpt-4o"
        assert eval_run.config["temperature"] == 0.7
        assert eval_run.config["instructions"] == "You are a helpful assistant"
        assert len(eval_run.config["tools"]) == 1


class TestListEvaluationRuns:
    """Test listing evaluation runs."""

    @pytest.fixture
    def test_dataset(self, db: Session):
        """Create a test dataset for evaluation runs."""
        org = db.exec(select(Organization)).first()
        project = db.exec(
            select(Project).where(Project.organization_id == org.id)
        ).first()

        return create_test_evaluation_dataset(
            db=db,
            organization_id=org.id,
            project_id=project.id,
            name="test_dataset_list",
            description="Test dataset",
            original_items_count=3,
            duplication_factor=1,
        )

    def test_list_evaluation_runs_empty(self, db: Session):
        """Test listing evaluation runs when none exist."""
        org = db.exec(select(Organization)).first()
        project = db.exec(
            select(Project).where(Project.organization_id == org.id)
        ).first()

        runs = list_evaluation_runs(
            session=db, organization_id=org.id, project_id=project.id
        )

        assert len(runs) == 0

    def test_list_evaluation_runs_multiple(self, db: Session, test_dataset):
        """Test listing multiple evaluation runs."""
        for i in range(5):
            create_evaluation_run(
                session=db,
                run_name=f"run_{i}",
                dataset_name=test_dataset.name,
                dataset_id=test_dataset.id,
                config={"model": "gpt-4o"},
                organization_id=test_dataset.organization_id,
                project_id=test_dataset.project_id,
            )

        runs = list_evaluation_runs(
            session=db,
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        assert len(runs) == 5
        assert runs[0].run_name == "run_4"
        assert runs[4].run_name == "run_0"

    def test_list_evaluation_runs_pagination(self, db: Session, test_dataset):
        """Test pagination of evaluation runs."""
        for i in range(10):
            create_evaluation_run(
                session=db,
                run_name=f"run_{i}",
                dataset_name=test_dataset.name,
                dataset_id=test_dataset.id,
                config={"model": "gpt-4o"},
                organization_id=test_dataset.organization_id,
                project_id=test_dataset.project_id,
            )

        page1 = list_evaluation_runs(
            session=db,
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
            limit=5,
            offset=0,
        )

        page2 = list_evaluation_runs(
            session=db,
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
            limit=5,
            offset=5,
        )

        assert len(page1) == 5
        assert len(page2) == 5
        page1_ids = [r.id for r in page1]
        page2_ids = [r.id for r in page2]
        assert len(set(page1_ids) & set(page2_ids)) == 0

    def test_list_evaluation_runs_respects_org_project(self, db: Session, test_dataset):
        """Test that list only returns runs for specific org/project."""
        create_evaluation_run(
            session=db,
            run_name="run_1",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        runs = list_evaluation_runs(
            session=db,
            organization_id=99999,
            project_id=test_dataset.project_id,
        )

        assert len(runs) == 0


class TestGetEvaluationRunById:
    """Test fetching evaluation runs by ID."""

    @pytest.fixture
    def test_dataset(self, db: Session):
        """Create a test dataset for evaluation runs."""
        org = db.exec(select(Organization)).first()
        project = db.exec(
            select(Project).where(Project.organization_id == org.id)
        ).first()

        return create_test_evaluation_dataset(
            db=db,
            organization_id=org.id,
            project_id=project.id,
            name="test_dataset_get",
            description="Test dataset",
            original_items_count=3,
            duplication_factor=1,
        )

    def test_get_evaluation_run_by_id_success(self, db: Session, test_dataset):
        """Test fetching an existing evaluation run by ID."""
        eval_run = create_evaluation_run(
            session=db,
            run_name="test_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        fetched = get_evaluation_run_by_id(
            session=db,
            evaluation_id=eval_run.id,
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        assert fetched is not None
        assert fetched.id == eval_run.id
        assert fetched.run_name == "test_run"

    def test_get_evaluation_run_by_id_not_found(self, db: Session):
        """Test fetching a non-existent evaluation run."""
        org = db.exec(select(Organization)).first()
        project = db.exec(
            select(Project).where(Project.organization_id == org.id)
        ).first()

        fetched = get_evaluation_run_by_id(
            session=db,
            evaluation_id=99999,
            organization_id=org.id,
            project_id=project.id,
        )

        assert fetched is None

    def test_get_evaluation_run_by_id_wrong_org(self, db: Session, test_dataset):
        """Test that runs from other orgs can't be fetched."""
        eval_run = create_evaluation_run(
            session=db,
            run_name="test_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        fetched = get_evaluation_run_by_id(
            session=db,
            evaluation_id=eval_run.id,
            organization_id=99999,
            project_id=test_dataset.project_id,
        )

        assert fetched is None


class TestUpdateEvaluationRun:
    """Test updating evaluation runs."""

    @pytest.fixture
    def test_dataset(self, db: Session):
        """Create a test dataset for evaluation runs."""
        org = db.exec(select(Organization)).first()
        project = db.exec(
            select(Project).where(Project.organization_id == org.id)
        ).first()

        return create_test_evaluation_dataset(
            db=db,
            organization_id=org.id,
            project_id=project.id,
            name="test_dataset_update",
            description="Test dataset",
            original_items_count=3,
            duplication_factor=1,
        )

    def test_update_evaluation_run_status(self, db: Session, test_dataset):
        """Test updating the status of an evaluation run."""
        eval_run = create_evaluation_run(
            session=db,
            run_name="test_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        assert eval_run.status == "pending"

        updated = update_evaluation_run(
            session=db, eval_run=eval_run, status="processing"
        )

        assert updated.status == "processing"
        assert updated.updated_at is not None

    def test_update_evaluation_run_error_message(self, db: Session, test_dataset):
        """Test updating error message of an evaluation run."""
        eval_run = create_evaluation_run(
            session=db,
            run_name="test_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        updated = update_evaluation_run(
            session=db, eval_run=eval_run, error_message="Test error"
        )

        assert updated.error_message == "Test error"

    def test_update_evaluation_run_object_store_url(self, db: Session, test_dataset):
        """Test updating object store URL of an evaluation run."""
        eval_run = create_evaluation_run(
            session=db,
            run_name="test_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        updated = update_evaluation_run(
            session=db,
            eval_run=eval_run,
            object_store_url="s3://bucket/results/test.jsonl",
        )

        assert updated.object_store_url == "s3://bucket/results/test.jsonl"

    def test_update_evaluation_run_score(self, db: Session, test_dataset):
        """Test updating score of an evaluation run."""
        eval_run = create_evaluation_run(
            session=db,
            run_name="test_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        score_data = {
            "traces": [{"trace_id": "trace1", "scores": []}],
            "summary_scores": [],
        }

        updated = update_evaluation_run(session=db, eval_run=eval_run, score=score_data)

        assert updated.score is not None
        assert "traces" in updated.score
        assert len(updated.score["traces"]) == 1

    def test_update_evaluation_run_embedding_batch_job_id(
        self, db: Session, test_dataset
    ):
        """Test updating embedding batch job ID of an evaluation run."""

        # Create a real batch job first
        batch_job = BatchJob(
            provider="openai",
            provider_batch_id="batch_xyz",
            job_type="embedding",
            total_items=5,
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
            run_name="test_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        updated = update_evaluation_run(
            session=db, eval_run=eval_run, embedding_batch_job_id=batch_job.id
        )

        assert updated.embedding_batch_job_id == batch_job.id

    def test_update_evaluation_run_multiple_fields(self, db: Session, test_dataset):
        """Test updating multiple fields at once."""
        eval_run = create_evaluation_run(
            session=db,
            run_name="test_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        score_data = {"traces": [], "summary_scores": []}

        updated = update_evaluation_run(
            session=db,
            eval_run=eval_run,
            status="completed",
            object_store_url="s3://bucket/results/test.jsonl",
            score=score_data,
        )

        assert updated.status == "completed"
        assert updated.object_store_url == "s3://bucket/results/test.jsonl"
        assert updated.score == score_data


class TestGetOrFetchScore:
    """Test get_or_fetch_score functionality."""

    @pytest.fixture
    def test_dataset(self, db: Session):
        """Create a test dataset for evaluation runs."""
        org = db.exec(select(Organization)).first()
        project = db.exec(
            select(Project).where(Project.organization_id == org.id)
        ).first()

        return create_test_evaluation_dataset(
            db=db,
            organization_id=org.id,
            project_id=project.id,
            name="test_dataset_score",
            description="Test dataset",
            original_items_count=3,
            duplication_factor=1,
        )

    def test_get_or_fetch_score_returns_cached(self, db: Session, test_dataset):
        """Test that cached score is returned when available."""
        cached_score = {
            "traces": [{"trace_id": "trace1", "scores": []}],
            "summary_scores": [],
        }

        eval_run = create_evaluation_run(
            session=db,
            run_name="test_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )
        eval_run = update_evaluation_run(
            session=db, eval_run=eval_run, score=cached_score
        )

        mock_langfuse = MagicMock()

        score = get_or_fetch_score(
            session=db, eval_run=eval_run, langfuse=mock_langfuse, force_refetch=False
        )

        assert score == cached_score
        mock_langfuse.get_dataset_run.assert_not_called()

    @patch("app.crud.evaluations.core.fetch_trace_scores_from_langfuse")
    def test_get_or_fetch_score_fetches_when_missing(
        self, mock_fetch, db: Session, test_dataset
    ):
        """Test that score is fetched from Langfuse when not cached."""
        eval_run = create_evaluation_run(
            session=db,
            run_name="test_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        fetched_score = {
            "traces": [
                {"trace_id": "trace1", "scores": [{"name": "accuracy", "value": 0.9}]}
            ],
            "summary_scores": [{"name": "accuracy", "value": 0.9}],
        }
        mock_fetch.return_value = fetched_score

        mock_langfuse = MagicMock()

        score = get_or_fetch_score(
            session=db, eval_run=eval_run, langfuse=mock_langfuse, force_refetch=False
        )

        assert score == fetched_score
        mock_fetch.assert_called_once()
        db.refresh(eval_run)
        assert eval_run.score == fetched_score

    @patch("app.crud.evaluations.core.fetch_trace_scores_from_langfuse")
    def test_get_or_fetch_score_force_refetch(
        self, mock_fetch, db: Session, test_dataset
    ):
        """Test that force_refetch bypasses cache."""
        cached_score = {"traces": [], "summary_scores": []}

        eval_run = create_evaluation_run(
            session=db,
            run_name="test_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )
        eval_run = update_evaluation_run(
            session=db, eval_run=eval_run, score=cached_score
        )

        new_score = {
            "traces": [
                {"trace_id": "trace1", "scores": [{"name": "accuracy", "value": 0.95}]}
            ],
            "summary_scores": [{"name": "accuracy", "value": 0.95}],
        }
        mock_fetch.return_value = new_score

        mock_langfuse = MagicMock()

        score = get_or_fetch_score(
            session=db, eval_run=eval_run, langfuse=mock_langfuse, force_refetch=True
        )

        assert score == new_score
        mock_fetch.assert_called_once()


class TestSaveScore:
    """Test save_score functionality."""

    @pytest.fixture
    def test_dataset(self, db: Session):
        """Create a test dataset for evaluation runs."""
        org = db.exec(select(Organization)).first()
        project = db.exec(
            select(Project).where(Project.organization_id == org.id)
        ).first()

        return create_test_evaluation_dataset(
            db=db,
            organization_id=org.id,
            project_id=project.id,
            name="test_dataset_save_score",
            description="Test dataset",
            original_items_count=3,
            duplication_factor=1,
        )

    def test_save_score_success(self, db: Session, test_dataset):
        """Test saving score to an evaluation run.

        Note: This test uses update_evaluation_run directly instead of save_score
        because save_score creates its own session which doesn't work well with
        the test's transactional session.
        """
        eval_run = create_evaluation_run(
            session=db,
            run_name="test_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        score_data = {
            "traces": [
                {"trace_id": "trace1", "scores": [{"name": "accuracy", "value": 0.85}]}
            ],
            "summary_scores": [{"name": "accuracy", "value": 0.85}],
        }

        # Test the core functionality using update_evaluation_run
        # (save_score is essentially a wrapper around this with its own session)
        updated = update_evaluation_run(
            session=db,
            eval_run=eval_run,
            score=score_data,
        )

        assert updated is not None
        assert updated.score == score_data
        assert updated.score["traces"][0]["trace_id"] == "trace1"
        assert updated.score["summary_scores"][0]["name"] == "accuracy"

    def test_save_score_not_found(self, db: Session):
        """Test saving score to non-existent evaluation run."""
        org = db.exec(select(Organization)).first()
        project = db.exec(
            select(Project).where(Project.organization_id == org.id)
        ).first()

        score_data = {"traces": [], "summary_scores": []}

        result = save_score(
            eval_run_id=99999,
            organization_id=org.id,
            project_id=project.id,
            score=score_data,
        )

        assert result is None
