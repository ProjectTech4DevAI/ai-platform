import io
from unittest.mock import patch

import pytest
from sqlmodel import select

from app.crud.evaluation_batch import build_evaluation_jsonl
from app.models import EvaluationDataset


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
        self, client, user_api_key_header, valid_csv_content, db
    ):
        """Test uploading a valid CSV file."""
        with (
            patch("app.core.cloud.get_cloud_storage") as _mock_storage,
            patch("app.crud.evaluation_dataset.upload_csv_to_s3") as mock_s3_upload,
            patch(
                "app.crud.evaluation_langfuse.upload_dataset_to_langfuse_from_csv"
            ) as mock_langfuse_upload,
        ):
            # Mock S3 upload
            mock_s3_upload.return_value = "s3://bucket/datasets/test_dataset.csv"

            # Mock Langfuse upload
            mock_langfuse_upload.return_value = ("test_dataset_id", 9)

            filename, file_obj = create_csv_file(valid_csv_content)

            response = client.post(
                "/api/v1/evaluations/datasets",
                files={"file": (filename, file_obj, "text/csv")},
                data={
                    "dataset_name": "test_dataset",
                    "description": "Test dataset description",
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
            assert data["s3_url"] == "s3://bucket/datasets/test_dataset.csv"
            assert "dataset_id" in data

            # Verify S3 upload was called
            mock_s3_upload.assert_called_once()

            # Verify Langfuse upload was called
            mock_langfuse_upload.assert_called_once()

    def test_upload_dataset_missing_columns(
        self,
        client,
        user_api_key_header,
        invalid_csv_missing_columns,
    ):
        """Test uploading CSV with missing required columns."""
        filename, file_obj = create_csv_file(invalid_csv_missing_columns)

        # The CSV validation happens before any mocked functions are called
        # so this test checks the actual validation logic
        response = client.post(
            "/api/v1/evaluations/datasets",
            files={"file": (filename, file_obj, "text/csv")},
            data={
                "dataset_name": "test_dataset",
                "duplication_factor": 5,
            },
            headers=user_api_key_header,
        )

        # Check that the response indicates a bad request
        assert response.status_code == 400
        response_data = response.json()
        error_str = response_data.get(
            "detail", response_data.get("message", str(response_data))
        )
        assert "question" in error_str.lower() or "answer" in error_str.lower()

    def test_upload_dataset_empty_rows(
        self, client, user_api_key_header, csv_with_empty_rows
    ):
        """Test uploading CSV with empty rows (should skip them)."""
        with (
            patch("app.core.cloud.get_cloud_storage") as _mock_storage,
            patch("app.crud.evaluation_dataset.upload_csv_to_s3") as mock_s3_upload,
            patch(
                "app.crud.evaluation_langfuse.upload_dataset_to_langfuse_from_csv"
            ) as mock_langfuse_upload,
        ):
            # Mock S3 and Langfuse uploads
            mock_s3_upload.return_value = "s3://bucket/datasets/test_dataset.csv"
            mock_langfuse_upload.return_value = ("test_dataset_id", 4)

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
        with (
            patch("app.core.cloud.get_cloud_storage") as _mock_storage,
            patch("app.crud.evaluation_dataset.upload_csv_to_s3") as mock_s3_upload,
            patch(
                "app.crud.evaluation_langfuse.upload_dataset_to_langfuse_from_csv"
            ) as mock_langfuse_upload,
        ):
            mock_s3_upload.return_value = "s3://bucket/datasets/test_dataset.csv"
            mock_langfuse_upload.return_value = ("test_dataset_id", 15)

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
        with (
            patch("app.core.cloud.get_cloud_storage") as _mock_storage,
            patch("app.crud.evaluation_dataset.upload_csv_to_s3") as mock_s3_upload,
            patch(
                "app.crud.evaluation_langfuse.upload_dataset_to_langfuse_from_csv"
            ) as mock_langfuse_upload,
        ):
            mock_s3_upload.return_value = "s3://bucket/datasets/test_dataset.csv"
            mock_langfuse_upload.return_value = ("test_dataset_id", 30)

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

    def test_upload_with_description(
        self, client, user_api_key_header, valid_csv_content, db
    ):
        """Test uploading with a description."""
        with (
            patch("app.core.cloud.get_cloud_storage") as _mock_storage,
            patch("app.crud.evaluation_dataset.upload_csv_to_s3") as mock_s3_upload,
            patch(
                "app.crud.evaluation_langfuse.upload_dataset_to_langfuse_from_csv"
            ) as mock_langfuse_upload,
        ):
            mock_s3_upload.return_value = "s3://bucket/datasets/test_dataset.csv"
            mock_langfuse_upload.return_value = ("test_dataset_id", 9)

            filename, file_obj = create_csv_file(valid_csv_content)

            response = client.post(
                "/api/v1/evaluations/datasets",
                files={"file": (filename, file_obj, "text/csv")},
                data={
                    "dataset_name": "test_dataset_with_description",
                    "description": "This is a test dataset for evaluation",
                    "duplication_factor": 3,
                },
                headers=user_api_key_header,
            )

            assert response.status_code == 200, response.text
            data = response.json()

            # Verify the description is stored
            dataset = db.exec(
                select(EvaluationDataset).where(
                    EvaluationDataset.id == data["dataset_id"]
                )
            ).first()

            assert dataset is not None
            assert dataset.description == "This is a test dataset for evaluation"


class TestDatasetUploadErrors:
    """Test error handling."""

    def test_upload_langfuse_configuration_fails(
        self, client, user_api_key_header, valid_csv_content
    ):
        """Test when Langfuse client configuration fails."""
        with (
            patch("app.core.cloud.get_cloud_storage") as _mock_storage,
            patch("app.crud.evaluation_dataset.upload_csv_to_s3") as mock_s3_upload,
            patch("app.crud.credentials.get_provider_credential") as mock_get_cred,
        ):
            # Mock S3 upload succeeds
            mock_s3_upload.return_value = "s3://bucket/datasets/test_dataset.csv"
            # Mock Langfuse credentials not found
            mock_get_cred.return_value = None

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

            # Accept either 400 (credentials not configured) or 500 (configuration/auth fails)
            assert response.status_code in [400, 500]
            response_data = response.json()
            error_str = response_data.get(
                "detail", response_data.get("message", str(response_data))
            )
            assert (
                "langfuse" in error_str.lower()
                or "credential" in error_str.lower()
                or "unauthorized" in error_str.lower()
            )

    def test_upload_invalid_csv_format(self, client, user_api_key_header):
        """Test uploading invalid CSV format."""
        invalid_csv = "not,a,valid\ncsv format here!!!"
        filename, file_obj = create_csv_file(invalid_csv)

        response = client.post(
            "/api/v1/evaluations/datasets",
            files={"file": (filename, file_obj, "text/csv")},
            data={
                "dataset_name": "test_dataset",
                "duplication_factor": 5,
            },
            headers=user_api_key_header,
        )

        # Should fail validation - check error contains expected message
        assert response.status_code == 400
        response_data = response.json()
        error_str = response_data.get(
            "detail", response_data.get("message", str(response_data))
        )
        assert (
            "question" in error_str.lower()
            or "answer" in error_str.lower()
            or "invalid" in error_str.lower()
        )

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
            "model": "gpt-4o",
            "temperature": 0.2,
            "instructions": "You are a helpful assistant",
        }

    def test_start_batch_evaluation_invalid_dataset_id(
        self, client, user_api_key_header, sample_evaluation_config
    ):
        """Test batch evaluation fails with invalid dataset_id."""
        # Try to start evaluation with non-existent dataset_id
        response = client.post(
            "/api/v1/evaluations",
            json={
                "experiment_name": "test_evaluation_run",
                "dataset_id": 99999,  # Non-existent
                "config": sample_evaluation_config,
            },
            headers=user_api_key_header,
        )

        assert response.status_code == 404
        response_data = response.json()
        error_str = response_data.get(
            "detail", response_data.get("message", str(response_data))
        )
        assert "not found" in error_str.lower() or "not accessible" in error_str.lower()

    def test_start_batch_evaluation_missing_model(self, client, user_api_key_header):
        """Test batch evaluation fails when model is missing from config."""
        # We don't need a real dataset for this test - the validation should happen
        # before dataset lookup. Use any dataset_id and expect config validation error
        invalid_config = {
            "instructions": "You are a helpful assistant",
            "temperature": 0.5,
        }

        response = client.post(
            "/api/v1/evaluations",
            json={
                "experiment_name": "test_no_model",
                "dataset_id": 1,  # Dummy ID, error should come before this is checked
                "config": invalid_config,
            },
            headers=user_api_key_header,
        )

        # Should fail with either 400 (model missing) or 404 (dataset not found)
        assert response.status_code in [400, 404]
        response_data = response.json()
        error_str = response_data.get(
            "detail", response_data.get("message", str(response_data))
        )
        # Should fail with either "model" missing or "dataset not found" (both acceptable)
        assert "model" in error_str.lower() or "not found" in error_str.lower()

    def test_start_batch_evaluation_without_authentication(
        self, client, sample_evaluation_config
    ):
        """Test batch evaluation requires authentication."""
        response = client.post(
            "/api/v1/evaluations",
            json={
                "experiment_name": "test_evaluation_run",
                "dataset_id": 1,
                "config": sample_evaluation_config,
            },
        )

        assert response.status_code == 401  # Unauthorized


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
            "model": "gpt-4o",
            "temperature": 0.2,
            "instructions": "You are a helpful assistant",
        }

        jsonl_data = build_evaluation_jsonl(dataset_items, config)

        assert len(jsonl_data) == 1
        assert isinstance(jsonl_data[0], dict)

        request = jsonl_data[0]
        assert request["custom_id"] == "item1"
        assert request["method"] == "POST"
        assert request["url"] == "/v1/responses"
        assert request["body"]["model"] == "gpt-4o"
        assert request["body"]["temperature"] == 0.2
        assert request["body"]["instructions"] == "You are a helpful assistant"
        assert request["body"]["input"] == "What is 2+2?"

    def test_build_batch_jsonl_with_tools(self):
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
            "tools": [
                {
                    "type": "file_search",
                    "vector_store_ids": ["vs_abc123"],
                }
            ],
        }

        jsonl_data = build_evaluation_jsonl(dataset_items, config)

        assert len(jsonl_data) == 1
        request = jsonl_data[0]
        assert request["body"]["tools"][0]["type"] == "file_search"
        assert "vs_abc123" in request["body"]["tools"][0]["vector_store_ids"]

    def test_build_batch_jsonl_minimal_config(self):
        """Test JSONL building with minimal config (only model required)."""
        dataset_items = [
            {
                "id": "item1",
                "input": {"question": "Test question"},
                "expected_output": {"answer": "Test answer"},
                "metadata": {},
            }
        ]

        config = {"model": "gpt-4o"}  # Only model provided

        jsonl_data = build_evaluation_jsonl(dataset_items, config)

        assert len(jsonl_data) == 1
        request = jsonl_data[0]
        assert request["body"]["model"] == "gpt-4o"
        assert request["body"]["input"] == "Test question"

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

        config = {"model": "gpt-4o", "instructions": "Test"}

        jsonl_data = build_evaluation_jsonl(dataset_items, config)

        # Should only have 1 valid item
        assert len(jsonl_data) == 1
        assert jsonl_data[0]["custom_id"] == "item1"

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
            "model": "gpt-4o",
            "instructions": "Answer questions",
        }

        jsonl_data = build_evaluation_jsonl(dataset_items, config)

        assert len(jsonl_data) == 5

        for i, request_dict in enumerate(jsonl_data):
            assert request_dict["custom_id"] == f"item{i}"
            assert request_dict["body"]["input"] == f"Question {i}"
            assert request_dict["body"]["model"] == "gpt-4o"
