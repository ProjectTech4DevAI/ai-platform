import pytest

from unittest.mock import patch, MagicMock

from app.tests.utils.test_data import create_test_fine_tuning_jobs
from app.tests.utils.utils import get_document
from app.models import Fine_Tuning


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
        document = get_document(db, "dalgo_sample.json")
        print("document = ", document)
        for path in ["/tmp/train.jsonl", "/tmp/test.jsonl"]:
            with open(path, "w") as f:
                f.write("{}")

        mock_preprocessor = MagicMock()
        mock_preprocessor.process.return_value = {
            "train_jsonl_temp_filepath": "/tmp/train.jsonl",
            "train_csv_s3_object": "s3://bucket/train.csv",
            "test_csv_s3_object": "s3://bucket/test.csv",
        }
        mock_preprocessor.cleanup = MagicMock()
        mock_preprocessor_cls.return_value = mock_preprocessor

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
            "system_prompt": "you are a model able to classify",
        }

        with patch("app.api.routes.fine_tuning.Session") as SessionMock:
            SessionMock.return_value.__enter__.return_value = db
            SessionMock.return_value.__exit__.return_value = None

            response = client.post(
                "/api/v1/fine_tuning/fine_tune",
                json=body,
                headers=user_api_key_header,
            )

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["message"] == "Fine-tuning job(s) started."
        assert json_data["metadata"] is None

        jobs = db.query(Fine_Tuning).all()
        assert len(jobs) == 3

        for i, job in enumerate(jobs, start=1):
            db.refresh(job)
            assert job.status == "running"
            assert job.provider_job_id == f"ft_mock_job_{i}"
            assert job.training_file_id is not None
            assert job.train_data_s3_object == "s3://bucket/train.csv"
            assert job.test_data_s3_object == "s3://bucket/test.csv"
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
