import pytest
from unittest.mock import patch, MagicMock
from openai import OpenAIError

from app.crud import fetch_by_id
from app.tests.utils.test_data import create_test_fine_tuning_jobs
from app.tests.utils.utils import get_user_from_api_key, get_document


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


@pytest.mark.usefixtures("client", "db", "user_api_key_header")
@patch("app.api.routes.fine_tuning.DataPreprocessor")
@patch("app.api.routes.fine_tuning.get_openai_client")
class TestCreateFineTuningJobAPI:
    def test_finetune_from_csv_multiple_split_ratio(
        self,
        mock_get_openai_client,
        mock_preprocessor_cls,
        client,
        db,
        user_api_key_header,
    ):
        user = get_user_from_api_key(db, user_api_key_header)
        document = get_document(db)

        for path in ["/tmp/train.jsonl", "/tmp/test.jsonl"]:
            with open(path, "w") as f:
                f.write("{}")

        mock_preprocessor_cls.return_value = MagicMock(
            process=MagicMock(
                return_value={
                    "train_file": "/tmp/train.jsonl",
                    "test_file": "/tmp/test.jsonl",
                }
            )
        )

        mock_openai = MagicMock()
        mock_openai.files.create.side_effect = create_file_mock("fine-tune")
        mock_openai.fine_tuning.jobs.create.side_effect = [
            MagicMock(id=f"ft_mock_job_{i}", status="running") for i in range(1, 4)
        ]
        mock_get_openai_client.return_value = mock_openai

        body = {
            "document_id": str(document.id),
            "base_model": "gpt-4",
            "split_ratio": [0.5, 0.7, 0.9],
        }

        response = client.post(
            "/api/v1/fine_tuning/fine-tune", json=body, headers=user_api_key_header
        )
        assert response.status_code == 200

        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["message"] == "Fine-tuning job(s) started."
        assert json_data["metadata"] is None

        for job in json_data["data"]["jobs"]:
            job_id = int(job["id"])
            job_db = fetch_by_id(db, job_id=job_id, project_id=user.project_id)
            assert job_db.training_file_id.startswith("file")
            assert job_db.testing_file_id.startswith("file")
            assert job_db.provider_job_id.startswith("ft_mock_job")
            assert job_db.status == "running"

    def test_data_preprocessing_failure(
        self,
        mock_get_openai_client,
        mock_preprocessor_cls,
        client,
        db,
        user_api_key_header,
    ):
        user = get_user_from_api_key(db, user_api_key_header)
        document = get_document(db)

        mock_preprocessor = MagicMock()
        mock_preprocessor.process.side_effect = ValueError("Invalid format")
        mock_preprocessor_cls.return_value = mock_preprocessor

        mock_get_openai_client.return_value = MagicMock()

        body = {
            "document_id": str(document.id),
            "base_model": "gpt-4",
            "split_ratio": [0.8],
        }

        response = client.post(
            "/api/v1/fine_tuning/fine-tune", json=body, headers=user_api_key_header
        )
        assert response.status_code == 200

        job_id = response.json()["data"]["jobs"][0]["id"]
        job = fetch_by_id(db, job_id, user.project_id)
        assert job.status == "failed"

    def test_openai_job_creation_failure(
        self,
        mock_get_openai_client,
        mock_preprocessor_cls,
        client,
        db,
        user_api_key_header,
    ):
        user = get_user_from_api_key(db, user_api_key_header)
        document = get_document(db)

        mock_preprocessor_cls.return_value = MagicMock(
            process=MagicMock(
                return_value={
                    "train_file": "/tmp/train.jsonl",
                    "test_file": "/tmp/test.jsonl",
                }
            )
        )

        openai_error = OpenAIError("Job create failed")
        openai_error.body = {"message": "Job create failed"}

        mock_openai = MagicMock()
        mock_openai.files.create.side_effect = create_file_mock("fine-tune")
        mock_openai.fine_tuning.jobs.create.side_effect = openai_error
        mock_get_openai_client.return_value = mock_openai

        body = {
            "document_id": str(document.id),
            "base_model": "gpt-4",
            "split_ratio": [0.8],
        }

        response = client.post(
            "/api/v1/fine_tuning/fine-tune", json=body, headers=user_api_key_header
        )
        print("resposneee=", response)
        assert response.status_code == 200

        job_id = response.json()["data"]["jobs"][0]["id"]
        job = fetch_by_id(db, job_id, user.project_id)
        assert job.status == "failed"


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
        document = get_document(db)

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
