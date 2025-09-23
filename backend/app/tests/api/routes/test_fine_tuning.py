import os
import io
import pytest
from moto import mock_aws
from unittest.mock import patch, MagicMock
import boto3

from app.tests.utils.test_data import create_test_fine_tuning_jobs
from app.tests.utils.utils import get_document
from app.models import (
    Fine_Tuning,
    FineTuningStatus,
    ModelEvaluation,
    ModelEvaluationStatus,
)
from app.core.config import settings


@pytest.fixture(scope="function")
def aws_credentials():
    """Set up AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["AWS_S3_BUCKET_PREFIX"] = "test-bucket"


def create_file_mock(file_type):
    counter = {"train": 0, "test": 0}

    def _side_effect(file=None, purpose=None):
        if purpose == "fine-tune":
            if "train" in file.name:
                counter["train"] += 1
                return MagicMock(id=f"file_{counter['train']}")
            elif "test" in file.name:
                counter["test"] += 1
                return MagicMock(id=f"file_{counter['test']}")

    return _side_effect


@pytest.mark.usefixtures("client", "db", "user_api_key_header", "aws_credentials")
class TestCreateFineTuningJobAPI:
    @mock_aws
    def test_finetune_from_csv_multiple_split_ratio(
        self,
        client,
        db,
        user_api_key_header,
    ):
        # Setup S3 bucket for moto
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")

        # Create a test CSV file content
        csv_content = "prompt,label\ntest1,label1\ntest2,label2\ntest3,label3"

        # Setup test files for preprocessing
        for path in ["/tmp/train.jsonl", "/tmp/test.jsonl"]:
            with open(path, "w") as f:
                f.write('{"prompt": "test", "completion": "label"}')

        with patch(
            "app.api.routes.fine_tuning.get_cloud_storage"
        ) as mock_get_cloud_storage:
            with patch(
                "app.api.routes.fine_tuning.get_openai_client"
            ) as mock_get_openai_client:
                with patch(
                    "app.api.routes.fine_tuning.process_fine_tuning_job"
                ) as mock_process_job:
                    # Mock cloud storage
                    mock_storage = MagicMock()
                    mock_storage.put.return_value = "s3://test-bucket/test.csv"
                    mock_get_cloud_storage.return_value = mock_storage

                    # Mock OpenAI client (for validation only)
                    mock_openai = MagicMock()
                    mock_get_openai_client.return_value = mock_openai

                    # Create file upload data
                    csv_file = io.BytesIO(csv_content.encode())
                    response = client.post(
                        "/api/v1/fine_tuning/fine_tune",
                        files={"file": ("test.csv", csv_file, "text/csv")},
                        data={
                            "base_model": "gpt-4",
                            "split_ratio": "0.5,0.7,0.9",
                            "system_prompt": "you are a model able to classify",
                        },
                        headers=user_api_key_header,
                    )

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["message"] == "Fine-tuning job(s) started."
        assert json_data["metadata"] is None
        assert "document_id" in json_data["data"]
        assert "jobs" in json_data["data"]
        assert len(json_data["data"]["jobs"]) == 3

        # Verify that the background task was called for each split ratio
        assert mock_process_job.call_count == 3

        jobs = db.query(Fine_Tuning).all()
        assert len(jobs) == 3

        for job in jobs:
            db.refresh(job)
            assert (
                job.status == "pending"
            )  # Since background processing is mocked, status remains pending
            assert job.split_ratio in [0.5, 0.7, 0.9]


@pytest.mark.usefixtures("client", "db", "user_api_key_header")
@patch("app.api.routes.fine_tuning.get_openai_client")
class TestRetriveFineTuningJobAPI:
    def test_retrieve_fine_tuning_job(
        self, mock_get_openai_client, client, db, user_api_key_header
    ):
        jobs, _ = create_test_fine_tuning_jobs(db, [0.3])
        job = jobs[0]
        job.provider_job_id = "ft_mock_job_123"
        db.flush()

        mock_openai_job = MagicMock(
            status="succeeded",
            fine_tuned_model="ft:gpt-4:custom-model",
            error=None,
        )

        mock_openai = MagicMock()
        mock_openai.fine_tuning.jobs.retrieve.return_value = mock_openai_job
        mock_get_openai_client.return_value = mock_openai

        response = client.get(
            f"/api/v1/fine_tuning/{job.id}/refresh", headers=user_api_key_header
        )

        assert response.status_code == 200
        json_data = response.json()

        assert json_data["data"]["status"] == "completed"
        assert json_data["data"]["fine_tuned_model"] == "ft:gpt-4:custom-model"
        assert json_data["data"]["id"] == job.id

    def test_retrieve_fine_tuning_job_failed(
        self, mock_get_openai_client, client, db, user_api_key_header
    ):
        jobs, _ = create_test_fine_tuning_jobs(db, [0.3])
        job = jobs[0]
        job.provider_job_id = "ft_mock_job_123"
        db.flush()

        mock_openai_job = MagicMock(
            status="failed",
            fine_tuned_model=None,
            error=MagicMock(message="Invalid file format for openai fine tuning"),
        )

        mock_openai = MagicMock()
        mock_openai.fine_tuning.jobs.retrieve.return_value = mock_openai_job
        mock_get_openai_client.return_value = mock_openai

        response = client.get(
            f"/api/v1/fine_tuning/{job.id}/refresh", headers=user_api_key_header
        )

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["data"]["status"] == "failed"
        assert (
            json_data["data"]["error_message"]
            == "Invalid file format for openai fine tuning"
        )
        assert json_data["data"]["id"] == job.id


@pytest.mark.usefixtures("client", "db", "user_api_key_header")
class TestFetchJob:
    def test_fetch_jobs_document(self, client, db, user_api_key_header):
        jobs, _ = create_test_fine_tuning_jobs(db, [0.3, 0.4])
        document = get_document(db, "dalgo_sample.json")

        response = client.get(
            f"/api/v1/fine_tuning/{document.id}", headers=user_api_key_header
        )
        assert response.status_code == 200
        json_data = response.json()

        assert json_data["success"] is True
        assert json_data["metadata"] is None
        assert len(json_data["data"]) == 2

        job_ratios = sorted([job["split_ratio"] for job in json_data["data"]])
        assert job_ratios == sorted([0.3, 0.4])

        for job in json_data["data"]:
            assert job["document_id"] == str(document.id)
            assert job["status"] == "pending"
