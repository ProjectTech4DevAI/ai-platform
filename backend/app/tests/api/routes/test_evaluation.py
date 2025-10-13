import io
from unittest.mock import patch, MagicMock
import pytest

from app.models.evaluation import DatasetUploadResponse


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


@pytest.fixture
def setup_credentials(db):
    """Setup mock credentials for Langfuse."""
    from app.crud.credentials import set_credentials

    credentials = {
        "langfuse": {
            "public_key": "test_public_key",
            "secret_key": "test_secret_key",
            "host": "https://cloud.langfuse.com",
        }
    }

    # Get organization_id from test user (from seed data)
    from sqlmodel import select
    from app.models import Organization

    org = db.exec(select(Organization)).first()

    set_credentials(
        session=db,
        org_id=org.id,
        credentials=credentials,
    )
    db.commit()
    return org.id


class TestDatasetUploadValidation:
    """Test CSV validation and parsing."""

    def test_upload_dataset_valid_csv(
        self, client, user_api_key_header, valid_csv_content, setup_credentials
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
                "/api/v1/dataset/upload",
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
        setup_credentials,
    ):
        """Test uploading CSV with missing required columns."""
        with patch("app.crud.evaluation.configure_langfuse") as mock_langfuse:
            mock_client = MagicMock()
            mock_langfuse.return_value = (mock_client, True)

            filename, file_obj = create_csv_file(invalid_csv_missing_columns)

            response = client.post(
                "/api/v1/dataset/upload",
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
        self, client, user_api_key_header, csv_with_empty_rows, setup_credentials
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
                "/api/v1/dataset/upload",
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

    def test_upload_dataset_no_langfuse_credentials(
        self, client, user_api_key_header, valid_csv_content
    ):
        """Test uploading without Langfuse credentials configured."""
        filename, file_obj = create_csv_file(valid_csv_content)

        response = client.post(
            "/api/v1/dataset/upload",
            files={"file": (filename, file_obj, "text/csv")},
            data={
                "dataset_name": "test_dataset",
                "duplication_factor": 5,
            },
            headers=user_api_key_header,
        )

        assert response.status_code == 500
        assert "LANGFUSE" in response.text or "not configured" in response.text.lower()


class TestDatasetUploadDuplication:
    """Test duplication logic."""

    def test_upload_with_default_duplication(
        self, client, user_api_key_header, valid_csv_content, setup_credentials
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
                "/api/v1/dataset/upload",
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
        self, client, user_api_key_header, valid_csv_content, setup_credentials
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
                "/api/v1/dataset/upload",
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
        self, client, user_api_key_header, valid_csv_content, setup_credentials
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
                "/api/v1/dataset/upload",
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
        self, client, user_api_key_header, valid_csv_content, setup_credentials
    ):
        """Test when Langfuse client configuration fails."""
        with patch("app.crud.evaluation.configure_langfuse") as mock_langfuse:
            mock_langfuse.return_value = (None, False)

            filename, file_obj = create_csv_file(valid_csv_content)

            response = client.post(
                "/api/v1/dataset/upload",
                files={"file": (filename, file_obj, "text/csv")},
                data={
                    "dataset_name": "test_dataset",
                    "duplication_factor": 5,
                },
                headers=user_api_key_header,
            )

            assert response.status_code == 500
            assert "Failed to configure" in response.text or "Langfuse" in response.text

    def test_upload_invalid_csv_format(
        self, client, user_api_key_header, setup_credentials
    ):
        """Test uploading invalid CSV format."""
        invalid_csv = "not,a,valid\ncsv format here!!!"
        filename, file_obj = create_csv_file(invalid_csv)

        with patch("app.crud.evaluation.configure_langfuse") as mock_langfuse:
            mock_client = MagicMock()
            mock_langfuse.return_value = (mock_client, True)

            response = client.post(
                "/api/v1/dataset/upload",
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
            "/api/v1/dataset/upload",
            files={"file": (filename, file_obj, "text/csv")},
            data={
                "dataset_name": "test_dataset",
                "duplication_factor": 5,
            },
        )

        assert response.status_code == 401  # Unauthorized
