from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, select

from app.crud.evaluations.batch import (
    build_evaluation_jsonl,
    fetch_dataset_items,
    start_evaluation_batch,
)
from app.crud.evaluations.core import create_evaluation_run
from app.models import BatchJob
from app.models import Organization, Project
from app.core.util import now
from app.tests.utils.test_data import create_test_evaluation_dataset


class TestFetchDatasetItems:
    """Test fetching dataset items from Langfuse."""

    def test_fetch_dataset_items_success(self):
        """Test successfully fetching dataset items."""
        mock_langfuse = MagicMock()
        mock_dataset = MagicMock()

        mock_item1 = MagicMock()
        mock_item1.id = "item1"
        mock_item1.input = {"question": "What is 2+2?"}
        mock_item1.expected_output = {"answer": "4"}
        mock_item1.metadata = {"category": "math"}

        mock_item2 = MagicMock()
        mock_item2.id = "item2"
        mock_item2.input = {"question": "What is the capital of France?"}
        mock_item2.expected_output = {"answer": "Paris"}
        mock_item2.metadata = {"category": "geography"}

        mock_dataset.items = [mock_item1, mock_item2]
        mock_langfuse.get_dataset.return_value = mock_dataset

        items = fetch_dataset_items(langfuse=mock_langfuse, dataset_name="test_dataset")

        assert len(items) == 2
        assert items[0]["id"] == "item1"
        assert items[0]["input"]["question"] == "What is 2+2?"
        assert items[0]["expected_output"]["answer"] == "4"
        assert items[0]["metadata"]["category"] == "math"
        assert items[1]["id"] == "item2"
        mock_langfuse.get_dataset.assert_called_once_with("test_dataset")

    def test_fetch_dataset_items_not_found(self):
        """Test fetching non-existent dataset."""
        mock_langfuse = MagicMock()
        mock_langfuse.get_dataset.side_effect = Exception("Dataset not found")

        with pytest.raises(ValueError, match="Dataset 'nonexistent' not found"):
            fetch_dataset_items(langfuse=mock_langfuse, dataset_name="nonexistent")

    def test_fetch_dataset_items_empty_dataset(self):
        """Test fetching dataset with no items."""
        mock_langfuse = MagicMock()
        mock_dataset = MagicMock()
        mock_dataset.items = []
        mock_langfuse.get_dataset.return_value = mock_dataset

        with pytest.raises(ValueError, match="Dataset 'empty_dataset' is empty"):
            fetch_dataset_items(langfuse=mock_langfuse, dataset_name="empty_dataset")

    def test_fetch_dataset_items_without_metadata(self):
        """Test fetching items without metadata attribute."""
        mock_langfuse = MagicMock()
        mock_dataset = MagicMock()

        mock_item = MagicMock(spec=["id", "input", "expected_output"])
        mock_item.id = "item1"
        mock_item.input = {"question": "Test"}
        mock_item.expected_output = {"answer": "Answer"}

        mock_dataset.items = [mock_item]
        mock_langfuse.get_dataset.return_value = mock_dataset

        items = fetch_dataset_items(langfuse=mock_langfuse, dataset_name="test_dataset")

        assert len(items) == 1
        assert items[0]["metadata"] == {}


class TestBuildEvaluationJsonl:
    """Test building JSONL for evaluation batch."""

    def test_build_evaluation_jsonl_basic(self):
        """Test basic JSONL building."""
        dataset_items = [
            {
                "id": "item1",
                "input": {"question": "What is 2+2?"},
                "expected_output": {"answer": "4"},
                "metadata": {},
            }
        ]

        config = {
            "model": "gpt-4o",
            "temperature": 0.2,
            "instructions": "You are a helpful assistant",
        }

        jsonl_data = build_evaluation_jsonl(dataset_items=dataset_items, config=config)

        assert len(jsonl_data) == 1
        request = jsonl_data[0]
        assert request["custom_id"] == "item1"
        assert request["method"] == "POST"
        assert request["url"] == "/v1/responses"
        assert request["body"]["model"] == "gpt-4o"
        assert request["body"]["temperature"] == 0.2
        assert request["body"]["instructions"] == "You are a helpful assistant"
        assert request["body"]["input"] == "What is 2+2?"

    def test_build_evaluation_jsonl_multiple_items(self):
        """Test JSONL building with multiple items."""
        dataset_items = [
            {
                "id": f"item{i}",
                "input": {"question": f"Question {i}"},
                "expected_output": {"answer": f"Answer {i}"},
                "metadata": {},
            }
            for i in range(5)
        ]

        config = {"model": "gpt-4o"}

        jsonl_data = build_evaluation_jsonl(dataset_items=dataset_items, config=config)

        assert len(jsonl_data) == 5
        for i, request in enumerate(jsonl_data):
            assert request["custom_id"] == f"item{i}"
            assert request["body"]["input"] == f"Question {i}"
            assert request["body"]["model"] == "gpt-4o"

    def test_build_evaluation_jsonl_with_tools(self):
        """Test JSONL building with tools configuration."""
        dataset_items = [
            {
                "id": "item1",
                "input": {"question": "Search the docs"},
                "expected_output": {"answer": "Answer from docs"},
                "metadata": {},
            }
        ]

        config = {
            "model": "gpt-4o-mini",
            "instructions": "Search documents",
            "tools": [{"type": "file_search", "vector_store_ids": ["vs_abc123"]}],
        }

        jsonl_data = build_evaluation_jsonl(dataset_items=dataset_items, config=config)

        assert len(jsonl_data) == 1
        request = jsonl_data[0]
        assert request["body"]["tools"][0]["type"] == "file_search"
        assert "vs_abc123" in request["body"]["tools"][0]["vector_store_ids"]

    def test_build_evaluation_jsonl_skips_empty_questions(self):
        """Test that items with empty questions are skipped."""
        dataset_items = [
            {
                "id": "item1",
                "input": {"question": "Valid question"},
                "expected_output": {"answer": "Answer"},
                "metadata": {},
            },
            {
                "id": "item2",
                "input": {"question": ""},  # Empty question
                "expected_output": {"answer": "Answer"},
                "metadata": {},
            },
            {
                "id": "item3",
                "input": {},  # Missing question key
                "expected_output": {"answer": "Answer"},
                "metadata": {},
            },
        ]

        config = {"model": "gpt-4o"}

        jsonl_data = build_evaluation_jsonl(dataset_items=dataset_items, config=config)

        # Should only have 1 valid item
        assert len(jsonl_data) == 1
        assert jsonl_data[0]["custom_id"] == "item1"

    def test_build_evaluation_jsonl_minimal_config(self):
        """Test JSONL building with minimal config (only model)."""
        dataset_items = [
            {
                "id": "item1",
                "input": {"question": "Test question"},
                "expected_output": {"answer": "Test answer"},
                "metadata": {},
            }
        ]

        config = {"model": "gpt-4o"}  # Only model provided

        jsonl_data = build_evaluation_jsonl(dataset_items=dataset_items, config=config)

        assert len(jsonl_data) == 1
        request = jsonl_data[0]
        assert request["body"]["model"] == "gpt-4o"
        assert request["body"]["input"] == "Test question"
        # Should not have other fields
        assert "temperature" not in request["body"]
        assert "instructions" not in request["body"]

    def test_build_evaluation_jsonl_preserves_all_config_fields(self):
        """Test that all config fields are preserved in the body."""
        dataset_items = [
            {
                "id": "item1",
                "input": {"question": "Test"},
                "expected_output": {"answer": "Answer"},
                "metadata": {},
            }
        ]

        config = {
            "model": "gpt-4o",
            "temperature": 0.8,
            "instructions": "Custom instructions",
            "reasoning": {"type": "auto"},
            "text": {"format": "json"},
            "include": ["content"],
        }

        jsonl_data = build_evaluation_jsonl(dataset_items=dataset_items, config=config)

        request = jsonl_data[0]
        assert request["body"]["model"] == "gpt-4o"
        assert request["body"]["temperature"] == 0.8
        assert request["body"]["instructions"] == "Custom instructions"
        assert request["body"]["reasoning"] == {"type": "auto"}
        assert request["body"]["text"] == {"format": "json"}
        assert request["body"]["include"] == ["content"]


class TestStartEvaluationBatch:
    """Test starting evaluation batch."""

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
            name="test_dataset_batch",
            description="Test dataset for batch",
            original_items_count=3,
            duplication_factor=1,
        )

    @patch("app.crud.evaluations.batch.fetch_dataset_items")
    @patch("app.crud.evaluations.batch.start_batch_job")
    def test_start_evaluation_batch_success(
        self, mock_start_batch, mock_fetch, db: Session, test_dataset
    ):
        """Test successfully starting an evaluation batch."""
        # Mock fetch_dataset_items
        mock_fetch.return_value = [
            {
                "id": "item1",
                "input": {"question": "What is 2+2?"},
                "expected_output": {"answer": "4"},
                "metadata": {},
            },
            {
                "id": "item2",
                "input": {"question": "What is 3+3?"},
                "expected_output": {"answer": "6"},
                "metadata": {},
            },
        ]

        # Create a real batch job in database
        mock_batch_job = BatchJob(
            provider="openai",
            provider_batch_id="batch_abc123",
            job_type="evaluation",
            total_items=2,
            status="submitted",
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
            inserted_at=now(),
            updated_at=now(),
        )
        db.add(mock_batch_job)
        db.commit()
        db.refresh(mock_batch_job)

        mock_start_batch.return_value = mock_batch_job

        # Create evaluation run
        eval_run = create_evaluation_run(
            session=db,
            run_name="test_batch_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        mock_langfuse = MagicMock()
        mock_openai = MagicMock()

        # Start batch
        updated_run = start_evaluation_batch(
            langfuse=mock_langfuse,
            openai_client=mock_openai,
            session=db,
            eval_run=eval_run,
            config={"model": "gpt-4o", "temperature": 0.2},
        )

        assert updated_run.batch_job_id == mock_batch_job.id
        assert updated_run.status == "processing"
        assert updated_run.total_items == 2
        mock_fetch.assert_called_once_with(
            langfuse=mock_langfuse, dataset_name=test_dataset.name
        )
        mock_start_batch.assert_called_once()

    @patch("app.crud.evaluations.batch.fetch_dataset_items")
    def test_start_evaluation_batch_empty_dataset(
        self, mock_fetch, db: Session, test_dataset
    ):
        """Test starting batch with empty dataset (no valid items)."""

        mock_fetch.return_value = [
            {
                "id": "item1",
                "input": {"question": ""},  # Empty question
                "expected_output": {"answer": "4"},
                "metadata": {},
            }
        ]

        eval_run = create_evaluation_run(
            session=db,
            run_name="test_batch_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        mock_langfuse = MagicMock()
        mock_openai = MagicMock()

        with pytest.raises(
            ValueError, match="did not produce any JSONL entries.*missing questions"
        ):
            start_evaluation_batch(
                langfuse=mock_langfuse,
                openai_client=mock_openai,
                session=db,
                eval_run=eval_run,
                config={"model": "gpt-4o"},
            )

        # Verify run status was updated to failed
        db.refresh(eval_run)
        assert eval_run.status == "failed"
        assert "did not produce any JSONL entries" in eval_run.error_message

    @patch("app.crud.evaluations.batch.fetch_dataset_items")
    def test_start_evaluation_batch_fetch_fails(
        self, mock_fetch, db: Session, test_dataset
    ):
        """Test starting batch when dataset fetch fails."""

        mock_fetch.side_effect = ValueError("Dataset not found in Langfuse")

        eval_run = create_evaluation_run(
            session=db,
            run_name="test_batch_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        mock_langfuse = MagicMock()
        mock_openai = MagicMock()

        with pytest.raises(ValueError, match="Dataset not found in Langfuse"):
            start_evaluation_batch(
                langfuse=mock_langfuse,
                openai_client=mock_openai,
                session=db,
                eval_run=eval_run,
                config={"model": "gpt-4o"},
            )

        # Verify run status was updated to failed
        db.refresh(eval_run)
        assert eval_run.status == "failed"
        assert "Dataset not found in Langfuse" in eval_run.error_message

    @patch("app.crud.evaluations.batch.fetch_dataset_items")
    @patch("app.crud.evaluations.batch.start_batch_job")
    def test_start_evaluation_batch_with_tools(
        self, mock_start_batch, mock_fetch, db: Session, test_dataset
    ):
        """Test starting batch with tools configuration."""
        mock_fetch.return_value = [
            {
                "id": "item1",
                "input": {"question": "Search the docs"},
                "expected_output": {"answer": "Answer"},
                "metadata": {},
            }
        ]

        # Create a real batch job in database
        mock_batch_job = BatchJob(
            provider="openai",
            provider_batch_id="batch_abc123",
            job_type="evaluation",
            total_items=1,
            status="submitted",
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
            inserted_at=now(),
            updated_at=now(),
        )
        db.add(mock_batch_job)
        db.commit()
        db.refresh(mock_batch_job)

        mock_start_batch.return_value = mock_batch_job

        eval_run = create_evaluation_run(
            session=db,
            run_name="test_batch_run",
            dataset_name=test_dataset.name,
            dataset_id=test_dataset.id,
            config={"model": "gpt-4o"},
            organization_id=test_dataset.organization_id,
            project_id=test_dataset.project_id,
        )

        mock_langfuse = MagicMock()
        mock_openai = MagicMock()

        config = {
            "model": "gpt-4o",
            "tools": [{"type": "file_search", "vector_store_ids": ["vs_123"]}],
        }

        updated_run = start_evaluation_batch(
            langfuse=mock_langfuse,
            openai_client=mock_openai,
            session=db,
            eval_run=eval_run,
            config=config,
        )

        assert updated_run.batch_job_id == mock_batch_job.id
        assert updated_run.status == "processing"

        # Verify that start_batch_job was called with correct config
        call_args = mock_start_batch.call_args
        jsonl_data = call_args.kwargs["jsonl_data"]
        assert len(jsonl_data) == 1
        assert jsonl_data[0]["body"]["tools"][0]["type"] == "file_search"
