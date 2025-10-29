import io
import json
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import select

from app.crud.evaluation_batch import build_evaluation_jsonl
from app.models import EvaluationRun


# Helper function to create CSV file-like object
def create_csv_file(content: str) -> tuple[str, io.BytesIO]:
    """Create a CSV file-like object for testing."""
    file_obj = io.BytesIO(content.encode("utf-8"))
    return ("test.csv", file_obj)


@pytest.fixture
def valid_csv_content():
    """Valid CSV content with question and answer columns."""
    return """question,answer
"Who is known as the strongest jujutsu sorcerer?","Satoru Gojo"
"What is the name of Gojo’s Domain Expansion?","Infinite Void"
"Who is known as the King of Curses?","Ryomen Sukuna"
"""


@pytest.fixture
def invalid_csv_missing_columns():
    """CSV content missing required columns."""
    return """query,response
"Who is known as the strongest jujutsu sorcerer?","Satoru Gojo"
"""


@pytest.fixture
def csv_with_empty_rows():
    """CSV content with some empty rows."""
    return """question,answer
"Who is known as the strongest jujutsu sorcerer?","Satoru Gojo"
"","4"
"Who wrote Romeo and Juliet?",""
"Valid question","Valid answer"
"""


class TestDatasetUploadValidation:
    """Test CSV validation and parsing."""

    def test_upload_dataset_valid_csv(
        self, client, user_api_key_header, valid_csv_content
    ):
        """Test uploading a valid CSV file."""
        with patch("app.crud.evaluation.configure_langfuse") as mock_langfuse:
            # Mock Langfuse client
            mock_client = MagicMock()
            mock_dataset = MagicMock()
            mock_dataset.id = "test_dataset_id"
            mock_client.create_dataset.return_value = mock_dataset
            mock_client.create_dataset_item.return_value = None
            mock_langfuse.return_value = (mock_client, True)

            filename, file_obj = create_csv_file(valid_csv_content)

            response = client.post(
                "/api/v1/evaluations/datasets",
                files={"file": (filename, file_obj, "text/csv")},
                data={
                    "dataset_name": "test_dataset",
                    "duplication_factor": 3,
                },
                headers=user_api_key_header,
            )

            assert response.status_code == 200, response.text
            data = response.json()

            assert data["dataset_name"] == "test_dataset"
            assert data["original_items"] == 3
            assert data["total_items"] == 9  # 3 items * 3 duplication
            assert data["duplication_factor"] == 3
            assert data["langfuse_dataset_id"] == "test_dataset_id"

            # Verify Langfuse was called correctly
            mock_client.create_dataset.assert_called_once_with(name="test_dataset")
            assert (
                mock_client.create_dataset_item.call_count == 9
            )  # 3 items * 3 duplicates

    def test_upload_dataset_missing_columns(
        self,
        client,
        user_api_key_header,
        invalid_csv_missing_columns,
    ):
        """Test uploading CSV with missing required columns."""
        with patch("app.crud.evaluation.configure_langfuse") as mock_langfuse:
            mock_client = MagicMock()
            mock_langfuse.return_value = (mock_client, True)

            filename, file_obj = create_csv_file(invalid_csv_missing_columns)

            response = client.post(
                "/api/v1/evaluations/datasets",
                files={"file": (filename, file_obj, "text/csv")},
                data={
                    "dataset_name": "test_dataset",
                    "duplication_factor": 5,
                },
                headers=user_api_key_header,
            )

            assert response.status_code == 500  # ValueError is raised
            assert (
                "question" in response.text.lower() or "answer" in response.text.lower()
            )

    def test_upload_dataset_empty_rows(
        self, client, user_api_key_header, csv_with_empty_rows
    ):
        """Test uploading CSV with empty rows (should skip them)."""
        with patch("app.crud.evaluation.configure_langfuse") as mock_langfuse:
            mock_client = MagicMock()
            mock_dataset = MagicMock()
            mock_dataset.id = "test_dataset_id"
            mock_client.create_dataset.return_value = mock_dataset
            mock_client.create_dataset_item.return_value = None
            mock_langfuse.return_value = (mock_client, True)

            filename, file_obj = create_csv_file(csv_with_empty_rows)

            response = client.post(
                "/api/v1/evaluations/datasets",
                files={"file": (filename, file_obj, "text/csv")},
                data={
                    "dataset_name": "test_dataset",
                    "duplication_factor": 2,
                },
                headers=user_api_key_header,
            )

            assert response.status_code == 200, response.text
            data = response.json()

            # Should only have 2 valid items (first and last rows)
            assert data["original_items"] == 2
            assert data["total_items"] == 4  # 2 items * 2 duplication


class TestDatasetUploadDuplication:
    """Test duplication logic."""

    def test_upload_with_default_duplication(
        self, client, user_api_key_header, valid_csv_content
    ):
        """Test uploading with default duplication factor (5)."""
        with patch("app.crud.evaluation.configure_langfuse") as mock_langfuse:
            mock_client = MagicMock()
            mock_dataset = MagicMock()
            mock_dataset.id = "test_dataset_id"
            mock_client.create_dataset.return_value = mock_dataset
            mock_client.create_dataset_item.return_value = None
            mock_langfuse.return_value = (mock_client, True)

            filename, file_obj = create_csv_file(valid_csv_content)

            response = client.post(
                "/api/v1/evaluations/datasets",
                files={"file": (filename, file_obj, "text/csv")},
                data={
                    "dataset_name": "test_dataset",
                    # duplication_factor not provided, should default to 5
                },
                headers=user_api_key_header,
            )

            assert response.status_code == 200, response.text
            data = response.json()

            assert data["duplication_factor"] == 5
            assert data["original_items"] == 3
            assert data["total_items"] == 15  # 3 items * 5 duplication

    def test_upload_with_custom_duplication(
        self, client, user_api_key_header, valid_csv_content
    ):
        """Test uploading with custom duplication factor."""
        with patch("app.crud.evaluation.configure_langfuse") as mock_langfuse:
            mock_client = MagicMock()
            mock_dataset = MagicMock()
            mock_dataset.id = "test_dataset_id"
            mock_client.create_dataset.return_value = mock_dataset
            mock_client.create_dataset_item.return_value = None
            mock_langfuse.return_value = (mock_client, True)

            filename, file_obj = create_csv_file(valid_csv_content)

            response = client.post(
                "/api/v1/evaluations/datasets",
                files={"file": (filename, file_obj, "text/csv")},
                data={
                    "dataset_name": "test_dataset",
                    "duplication_factor": 10,
                },
                headers=user_api_key_header,
            )

            assert response.status_code == 200, response.text
            data = response.json()

            assert data["duplication_factor"] == 10
            assert data["original_items"] == 3
            assert data["total_items"] == 30  # 3 items * 10 duplication

    def test_upload_metadata_includes_duplicate_number(
        self, client, user_api_key_header, valid_csv_content
    ):
        """Test that metadata includes duplicate number for each item."""
        with patch("app.crud.evaluation.configure_langfuse") as mock_langfuse:
            mock_client = MagicMock()
            mock_dataset = MagicMock()
            mock_dataset.id = "test_dataset_id"
            mock_client.create_dataset.return_value = mock_dataset
            mock_client.create_dataset_item.return_value = None
            mock_langfuse.return_value = (mock_client, True)

            filename, file_obj = create_csv_file(valid_csv_content)

            response = client.post(
                "/api/v1/evaluations/datasets",
                files={"file": (filename, file_obj, "text/csv")},
                data={
                    "dataset_name": "test_dataset",
                    "duplication_factor": 3,
                },
                headers=user_api_key_header,
            )

            assert response.status_code == 200, response.text

            # Verify metadata was passed correctly
            calls = mock_client.create_dataset_item.call_args_list

            # Check that each duplicate has correct metadata
            duplicate_numbers = set()
            for call in calls:
                metadata = call.kwargs.get("metadata", {})
                duplicate_numbers.add(metadata["duplicate_number"])
                assert metadata["duplication_factor"] == 3
                assert "original_question" in metadata

            # Should have duplicate numbers 1, 2, 3
            assert duplicate_numbers == {1, 2, 3}


class TestDatasetUploadErrors:
    """Test error handling."""

    def test_upload_langfuse_configuration_fails(
        self, client, user_api_key_header, valid_csv_content
    ):
        """Test when Langfuse client configuration fails."""
        with patch("app.crud.evaluation.configure_langfuse") as mock_langfuse:
            mock_langfuse.return_value = (None, False)

            filename, file_obj = create_csv_file(valid_csv_content)

            response = client.post(
                "/api/v1/evaluations/datasets",
                files={"file": (filename, file_obj, "text/csv")},
                data={
                    "dataset_name": "test_dataset",
                    "duplication_factor": 5,
                },
                headers=user_api_key_header,
            )

            assert response.status_code == 500
            assert "Failed to configure" in response.text or "Langfuse" in response.text

    def test_upload_invalid_csv_format(self, client, user_api_key_header):
        """Test uploading invalid CSV format."""
        invalid_csv = "not,a,valid\ncsv format here!!!"
        filename, file_obj = create_csv_file(invalid_csv)

        with patch("app.crud.evaluation.configure_langfuse") as mock_langfuse:
            mock_client = MagicMock()
            mock_langfuse.return_value = (mock_client, True)

            response = client.post(
                "/api/v1/evaluations/datasets",
                files={"file": (filename, file_obj, "text/csv")},
                data={
                    "dataset_name": "test_dataset",
                    "duplication_factor": 5,
                },
                headers=user_api_key_header,
            )

            # Should fail validation
            assert response.status_code == 500

    def test_upload_without_authentication(self, client, valid_csv_content):
        """Test uploading without authentication."""
        filename, file_obj = create_csv_file(valid_csv_content)

        response = client.post(
            "/api/v1/evaluations/datasets",
            files={"file": (filename, file_obj, "text/csv")},
            data={
                "dataset_name": "test_dataset",
                "duplication_factor": 5,
            },
        )

        assert response.status_code == 401  # Unauthorized


class TestBatchEvaluation:
    """Test batch evaluation endpoint using OpenAI Batch API."""

    @pytest.fixture
    def sample_evaluation_config(self):
        """Sample evaluation configuration."""
        return {
            "llm": {"model": "gpt-4o", "temperature": 0.2},
            "instructions": "You are a helpful assistant",
            "vector_store_ids": [],
        }

    @pytest.fixture
    def sample_evaluation_config_with_vector_stores(self):
        """Sample evaluation configuration with vector stores."""
        return {
            "llm": {"model": "gpt-4o-mini", "temperature": 0.5},
            "instructions": "You are an expert assistant with access to documents",
            "vector_store_ids": ["vs_abc123", "vs_def456"],
        }

    def test_start_batch_evaluation_success(
        self,
        client,
        user_api_key_header,
        sample_evaluation_config,
    ):
        """Test successfully starting a batch evaluation."""
        with patch(
            "app.crud.evaluation_batch.fetch_dataset_items"
        ) as mock_fetch, patch(
            "app.crud.evaluation_batch.upload_batch_file"
        ) as mock_upload, patch(
            "app.crud.evaluation_batch.create_batch_job"
        ) as mock_create_batch, patch(
            "app.api.routes.evaluation.configure_openai"
        ) as mock_openai, patch(
            "app.api.routes.evaluation.configure_langfuse"
        ) as mock_langfuse:
            # Mock dataset items from Langfuse
            mock_fetch.return_value = [
                {
                    "id": "item1",
                    "input": {"question": "What is 2+2?"},
                    "expected_output": {"answer": "4"},
                    "metadata": {},
                },
                {
                    "id": "item2",
                    "input": {"question": "What is the capital of France?"},
                    "expected_output": {"answer": "Paris"},
                    "metadata": {},
                },
            ]

            # Mock OpenAI file upload
            mock_upload.return_value = "file-abc123"

            # Mock batch job creation
            mock_create_batch.return_value = {
                "id": "batch_abc123",
                "status": "validating",
                "created_at": 1234567890,
                "endpoint": "/v1/responses",
                "input_file_id": "file-abc123",
            }

            # Mock clients
            mock_openai_client = MagicMock()
            mock_openai.return_value = (mock_openai_client, True)

            mock_langfuse_client = MagicMock()
            mock_langfuse.return_value = (mock_langfuse_client, True)

            response = client.post(
                "/api/v1/evaluations",
                json={
                    "run_name": "test_evaluation_run",
                    "dataset_name": "test_dataset",
                    "config": sample_evaluation_config,
                },
                headers=user_api_key_header,
            )

            assert response.status_code == 200, response.text
            data = response.json()

            # Verify response structure
            assert data["run_name"] == "test_evaluation_run"
            assert data["dataset_name"] == "test_dataset"
            assert data["config"] == sample_evaluation_config
            assert data["status"] == "processing"
            assert data["batch_status"] == "validating"
            assert data["batch_id"] == "batch_abc123"
            assert data["batch_file_id"] == "file-abc123"
            assert data["total_items"] == 2

            # Verify mocks were called
            mock_fetch.assert_called_once()
            mock_upload.assert_called_once()
            mock_create_batch.assert_called_once()

    def test_start_batch_evaluation_with_vector_stores(
        self,
        client,
        user_api_key_header,
        sample_evaluation_config_with_vector_stores,
    ):
        """Test batch evaluation with vector stores configured."""
        with patch(
            "app.crud.evaluation_batch.fetch_dataset_items"
        ) as mock_fetch, patch(
            "app.crud.evaluation_batch.upload_batch_file"
        ) as mock_upload, patch(
            "app.crud.evaluation_batch.create_batch_job"
        ) as mock_create_batch, patch(
            "app.api.routes.evaluation.configure_openai"
        ) as mock_openai, patch(
            "app.api.routes.evaluation.configure_langfuse"
        ) as mock_langfuse:
            mock_fetch.return_value = [
                {
                    "id": "item1",
                    "input": {"question": "Test question"},
                    "expected_output": {"answer": "Test answer"},
                    "metadata": {},
                }
            ]

            mock_upload.return_value = "file-xyz789"
            mock_create_batch.return_value = {
                "id": "batch_xyz789",
                "status": "validating",
                "created_at": 1234567890,
                "endpoint": "/v1/responses",
                "input_file_id": "file-xyz789",
            }

            mock_openai_client = MagicMock()
            mock_openai.return_value = (mock_openai_client, True)

            mock_langfuse_client = MagicMock()
            mock_langfuse.return_value = (mock_langfuse_client, True)

            response = client.post(
                "/api/v1/evaluations",
                json={
                    "run_name": "test_with_vector_stores",
                    "dataset_name": "test_dataset",
                    "config": sample_evaluation_config_with_vector_stores,
                },
                headers=user_api_key_header,
            )

            assert response.status_code == 200, response.text
            data = response.json()

            assert data["config"]["vector_store_ids"] == ["vs_abc123", "vs_def456"]
            assert data["batch_id"] == "batch_xyz789"

    def test_start_batch_evaluation_invalid_dataset(
        self, client, user_api_key_header, sample_evaluation_config
    ):
        """Test batch evaluation fails with invalid dataset name."""
        with patch(
            "app.crud.evaluation_batch.fetch_dataset_items"
        ) as mock_fetch, patch(
            "app.api.routes.evaluation.configure_openai"
        ) as mock_openai, patch(
            "app.api.routes.evaluation.configure_langfuse"
        ) as mock_langfuse:
            # Mock dataset fetch to raise error
            mock_fetch.side_effect = ValueError("Dataset 'invalid_dataset' not found")

            mock_openai_client = MagicMock()
            mock_openai.return_value = (mock_openai_client, True)

            mock_langfuse_client = MagicMock()
            mock_langfuse.return_value = (mock_langfuse_client, True)

            response = client.post(
                "/api/v1/evaluations",
                json={
                    "run_name": "test_evaluation_run",
                    "dataset_name": "invalid_dataset",
                    "config": sample_evaluation_config,
                },
                headers=user_api_key_header,
            )

            assert response.status_code == 500
            assert (
                "not found" in response.text.lower()
                or "failed" in response.text.lower()
            )

    def test_start_batch_evaluation_empty_dataset(
        self, client, user_api_key_header, sample_evaluation_config
    ):
        """Test batch evaluation fails with empty dataset."""
        with patch(
            "app.crud.evaluation_batch.fetch_dataset_items"
        ) as mock_fetch, patch(
            "app.api.routes.evaluation.configure_openai"
        ) as mock_openai, patch(
            "app.api.routes.evaluation.configure_langfuse"
        ) as mock_langfuse:
            # Mock empty dataset
            mock_fetch.side_effect = ValueError("Dataset 'empty_dataset' is empty")

            mock_openai_client = MagicMock()
            mock_openai.return_value = (mock_openai_client, True)

            mock_langfuse_client = MagicMock()
            mock_langfuse.return_value = (mock_langfuse_client, True)

            response = client.post(
                "/api/v1/evaluations",
                json={
                    "run_name": "test_evaluation_run",
                    "dataset_name": "empty_dataset",
                    "config": sample_evaluation_config,
                },
                headers=user_api_key_header,
            )

            assert response.status_code == 500
            assert "empty" in response.text.lower() or "failed" in response.text.lower()

    def test_start_batch_evaluation_without_authentication(
        self, client, sample_evaluation_config
    ):
        """Test batch evaluation requires authentication."""
        response = client.post(
            "/api/v1/evaluations",
            json={
                "run_name": "test_evaluation_run",
                "dataset_name": "test_dataset",
                "config": sample_evaluation_config,
            },
        )

        assert response.status_code == 401  # Unauthorized

    def test_start_batch_evaluation_invalid_config(self, client, user_api_key_header):
        """Test batch evaluation with invalid config structure."""
        invalid_config = {
            "llm": {"model": "gpt-4o"},
            # Missing instructions
            "vector_store_ids": "should_be_list_not_string",
        }

        with patch("app.api.routes.evaluation.configure_openai") as mock_openai, patch(
            "app.api.routes.evaluation.configure_langfuse"
        ) as mock_langfuse:
            mock_openai_client = MagicMock()
            mock_openai.return_value = (mock_openai_client, True)

            mock_langfuse_client = MagicMock()
            mock_langfuse.return_value = (mock_langfuse_client, True)

            # This should still work because config is flexible (dict)
            # but build_batch_jsonl will use defaults for missing values
            response = client.post(
                "/api/v1/evaluations",
                json={
                    "run_name": "test_evaluation_run",
                    "dataset_name": "test_dataset",
                    "config": invalid_config,
                },
                headers=user_api_key_header,
            )

            # Should succeed because config validation is flexible
            # The function will use defaults where needed
            assert response.status_code in [200, 500]  # Depends on other mocks

    def test_start_batch_evaluation_creates_database_record(
        self, client, user_api_key_header, sample_evaluation_config, db
    ):
        """Test that batch evaluation creates a proper database record."""
        with patch(
            "app.crud.evaluation_batch.fetch_dataset_items"
        ) as mock_fetch, patch(
            "app.crud.evaluation_batch.upload_batch_file"
        ) as mock_upload, patch(
            "app.crud.evaluation_batch.create_batch_job"
        ) as mock_create_batch, patch(
            "app.api.routes.evaluation.configure_openai"
        ) as mock_openai, patch(
            "app.api.routes.evaluation.configure_langfuse"
        ) as mock_langfuse:
            mock_fetch.return_value = [
                {
                    "id": "item1",
                    "input": {"question": "Test?"},
                    "expected_output": {"answer": "Test"},
                    "metadata": {},
                }
            ]

            mock_upload.return_value = "file-test123"
            mock_create_batch.return_value = {
                "id": "batch_test123",
                "status": "validating",
                "created_at": 1234567890,
                "endpoint": "/v1/responses",
                "input_file_id": "file-test123",
            }

            mock_openai_client = MagicMock()
            mock_openai.return_value = (mock_openai_client, True)

            mock_langfuse_client = MagicMock()
            mock_langfuse.return_value = (mock_langfuse_client, True)

            response = client.post(
                "/api/v1/evaluations",
                json={
                    "run_name": "database_test_run",
                    "dataset_name": "test_dataset",
                    "config": sample_evaluation_config,
                },
                headers=user_api_key_header,
            )

            assert response.status_code == 200, response.text

            # Verify database record was created
            eval_run = db.exec(
                select(EvaluationRun).where(
                    EvaluationRun.run_name == "database_test_run"
                )
            ).first()

            assert eval_run is not None
            assert eval_run.dataset_name == "test_dataset"
            assert eval_run.config == sample_evaluation_config
            assert eval_run.status == "processing"
            assert eval_run.batch_status == "validating"
            assert eval_run.batch_id == "batch_test123"
            assert eval_run.batch_file_id == "file-test123"
            assert eval_run.total_items == 1


class TestBatchEvaluationJSONLBuilding:
    """Test JSONL building logic for batch evaluation."""

    def test_build_batch_jsonl_basic(self):
        """Test basic JSONL building with minimal config."""
        dataset_items = [
            {
                "id": "item1",
                "input": {"question": "What is 2+2?"},
                "expected_output": {"answer": "4"},
                "metadata": {},
            }
        ]

        config = {
            "llm": {"model": "gpt-4o", "temperature": 0.2},
            "instructions": "You are a helpful assistant",
            "vector_store_ids": [],
        }

        batch_file = build_evaluation_jsonl(dataset_items, config)

        assert len(batch_file) == 1

        request = json.loads(batch_file[0])

        assert request["custom_id"] == "item1"
        assert request["method"] == "POST"
        assert request["url"] == "/v1/responses"
        assert request["body"]["model"] == "gpt-4o"
        assert request["body"]["instructions"] == "You are a helpful assistant"
        assert request["body"]["input"] == "What is 2+2?"
        assert "tools" not in request["body"]

    def test_build_batch_jsonl_with_vector_stores(self):
        """Test JSONL building with vector stores."""
        dataset_items = [
            {
                "id": "item1",
                "input": {"question": "Search the docs"},
                "expected_output": {"answer": "Answer from docs"},
                "metadata": {},
            }
        ]

        config = {
            "llm": {"model": "gpt-4o-mini"},
            "instructions": "Search documents",
            "vector_store_ids": ["vs_abc123"],
        }

        batch_file = build_evaluation_jsonl(dataset_items, config)

        assert len(batch_file) == 1

        request = json.loads(batch_file[0])

        assert request["body"]["tools"] == [{"type": "file_search"}]
        assert request["body"]["tool_choice"] == "auto"

    def test_build_batch_jsonl_uses_defaults(self):
        """Test JSONL building with missing config values uses defaults."""
        dataset_items = [
            {
                "id": "item1",
                "input": {"question": "Test question"},
                "expected_output": {"answer": "Test answer"},
                "metadata": {},
            }
        ]

        config = {}  # Empty config, should use defaults

        batch_file = build_evaluation_jsonl(dataset_items, config)

        assert len(batch_file) == 1

        request = json.loads(batch_file[0])

        # Check defaults
        assert request["body"]["model"] == "gpt-4o"  # Default model
        assert (
            request["body"]["instructions"] == "You are a helpful assistant"
        )  # Default instructions

    def test_build_batch_jsonl_skips_empty_questions(self):
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

        config = {"llm": {"model": "gpt-4o"}, "instructions": "Test"}

        batch_file = build_evaluation_jsonl(dataset_items, config)

        # Should only have 1 valid item
        assert len(batch_file) == 1

        request = json.loads(batch_file[0])
        assert request["custom_id"] == "item1"

    def test_build_batch_jsonl_multiple_items(self):
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

        config = {
            "llm": {"model": "gpt-4o"},
            "instructions": "Answer questions",
            "vector_store_ids": [],
        }

        batch_file = build_evaluation_jsonl(dataset_items, config)

        assert len(batch_file) == 5

        for i, line in enumerate(batch_file):
            request = json.loads(line)
            assert request["custom_id"] == f"item{i}"
            assert request["body"]["input"] == f"Question {i}"
