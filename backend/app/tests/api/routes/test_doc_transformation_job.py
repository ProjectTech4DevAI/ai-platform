from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.crud.document.doc_transformation_job import DocTransformationJobCrud
from app.models import TransformationStatus
from app.tests.utils.document import DocumentStore
from app.tests.utils.auth import TestAuthContext


class TestGetTransformationJob:
    def test_get_existing_job_success(
        self, client: TestClient, db: Session, user_api_key: TestAuthContext
    ):
        """Test successfully retrieving an existing transformation job."""
        document = DocumentStore(db, user_api_key.project_id).put()
        job = DocTransformationJobCrud(db, user_api_key.project_id)
        created_job = job.create(document.id)

        response = client.get(
            f"{settings.API_V1_STR}/documents/transformations/{created_job.id}",
            headers={"X-API-KEY": user_api_key.key},
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert data["data"]["id"] is not None
        assert data["data"]["source_document_id"] == str(document.id)
        assert data["data"]["status"] == TransformationStatus.PENDING
        assert data["data"]["error_message"] is None
        assert data["data"]["transformed_document_id"] is None

    def test_get_nonexistent_job_404(
        self, client: TestClient, db: Session, user_api_key: TestAuthContext
    ):
        """Test getting a non-existent transformation job returns 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000001"

        response = client.get(
            f"{settings.API_V1_STR}/documents/transformations/{fake_uuid}",
            headers={"X-API-KEY": user_api_key.key},
        )

        assert response.status_code == 404

    def test_get_job_invalid_uuid_422(
        self, client: TestClient, user_api_key: TestAuthContext
    ):
        """Test getting a job with invalid UUID format returns 422."""
        invalid_uuid = "not-a-uuid"

        response = client.get(
            f"{settings.API_V1_STR}/documents/transformations/{invalid_uuid}",
            headers={"X-API-KEY": user_api_key.key},
        )

        assert response.status_code == 422

    def test_get_job_different_project_404(
        self,
        client: TestClient,
        db: Session,
        user_api_key: TestAuthContext,
        superuser_api_key: TestAuthContext,
    ):
        """Test that jobs from different projects are not accessible."""
        store = DocumentStore(db, user_api_key.project_id)
        crud = DocTransformationJobCrud(db, user_api_key.project_id)
        document = store.put()
        job = crud.create(document.id)

        # Try to access with user from different project (superuser)
        response = client.get(
            f"{settings.API_V1_STR}/documents/transformations/{job.id}",
            headers={"X-API-KEY": superuser_api_key.key},
        )

        assert response.status_code == 404

    def test_get_completed_job_with_result(
        self, client: TestClient, db: Session, user_api_key: TestAuthContext
    ):
        """Test getting a completed job with transformation result."""
        store = DocumentStore(db, user_api_key.project_id)
        crud = DocTransformationJobCrud(db, user_api_key.project_id)
        source_document = store.put()
        transformed_document = store.put()
        job = crud.create(source_document.id)

        # Update job to completed status
        crud.update_status(
            job.id,
            TransformationStatus.COMPLETED,
            transformed_document_id=transformed_document.id,
        )

        response = client.get(
            f"{settings.API_V1_STR}/documents/transformations/{job.id}",
            headers={"X-API-KEY": user_api_key.key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == TransformationStatus.COMPLETED
        assert data["data"]["transformed_document_id"] == str(transformed_document.id)

    def test_get_failed_job_with_error(
        self, client: TestClient, db: Session, user_api_key: TestAuthContext
    ):
        """Test getting a failed job with error message."""
        store = DocumentStore(db, user_api_key.project_id)
        crud = DocTransformationJobCrud(db, user_api_key.project_id)
        document = store.put()
        job = crud.create(document.id)
        error_msg = "Transformation failed due to invalid format"

        # Update job to failed status
        crud.update_status(job.id, TransformationStatus.FAILED, error_message=error_msg)

        response = client.get(
            f"{settings.API_V1_STR}/documents/transformations/{job.id}",
            headers={"X-API-KEY": user_api_key.key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == TransformationStatus.FAILED
        assert data["data"]["error_message"] == error_msg


class TestGetMultipleTransformationJobs:
    def test_get_multiple_jobs_success(
        self, client: TestClient, db: Session, user_api_key: TestAuthContext
    ):
        """Test successfully retrieving multiple transformation jobs."""
        store = DocumentStore(db, user_api_key.project_id)
        crud = DocTransformationJobCrud(db, user_api_key.project_id)
        documents = store.fill(3)
        jobs = [crud.create(doc.id) for doc in documents]
        job_ids_params = "&".join(f"job_ids={job.id}" for job in jobs)

        response = client.get(
            f"{settings.API_V1_STR}/documents/transformations/?{job_ids_params}",
            headers={"X-API-KEY": user_api_key.key},
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]["jobs"]) == 3
        assert len(data["data"]["jobs_not_found"]) == 0

        returned_ids = {job["id"] for job in data["data"]["jobs"]}
        expected_ids = {str(job.id) for job in jobs}
        assert returned_ids == expected_ids

    def test_get_mixed_existing_nonexisting_jobs(
        self, client: TestClient, db: Session, user_api_key: TestAuthContext
    ):
        """Test retrieving a mix of existing and non-existing jobs."""
        store = DocumentStore(db, user_api_key.project_id)
        crud = DocTransformationJobCrud(db, user_api_key.project_id)
        documents = store.fill(2)
        jobs = [crud.create(doc.id) for doc in documents]
        fake_uuid = "00000000-0000-0000-0000-000000000001"

        job_ids_params = (
            f"job_ids={jobs[0].id}&job_ids={jobs[1].id}&job_ids={fake_uuid}"
        )

        response = client.get(
            f"{settings.API_V1_STR}/documents/transformations/?{job_ids_params}",
            headers={"X-API-KEY": user_api_key.key},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["jobs"]) == 2
        assert len(data["data"]["jobs_not_found"]) == 1
        assert data["data"]["jobs_not_found"][0] == fake_uuid

    def test_get_jobs_with_empty_string(
        self, client: TestClient, user_api_key: TestAuthContext
    ):
        """Test retrieving jobs with empty job_ids parameter."""
        response = client.get(
            f"{settings.API_V1_STR}/documents/transformations/?job_ids=",
            headers={"X-API-KEY": user_api_key.key},
        )

        assert response.status_code == 422

    def test_get_jobs_with_whitespace_only(
        self, client: TestClient, user_api_key: TestAuthContext
    ):
        """Test retrieving jobs with whitespace-only job_ids."""
        response = client.get(
            f"{settings.API_V1_STR}/documents/transformations/?job_ids=   ",
            headers={"X-API-KEY": user_api_key.key},
        )

        assert response.status_code == 422

    def test_get_jobs_invalid_uuid_format_422(
        self, client: TestClient, user_api_key: TestAuthContext
    ):
        """Test that invalid UUID format returns 422."""
        invalid_uuid = "not-a-uuid"

        response = client.get(
            f"{settings.API_V1_STR}/documents/transformations/?job_ids={invalid_uuid}",
            headers={"X-API-KEY": user_api_key.key},
        )

        assert response.status_code == 422
        data = response.json()
        assert "Input should be a valid UUID" in data["error"]

    def test_get_jobs_mixed_valid_invalid_uuid_422(
        self, client: TestClient, db: Session, user_api_key: TestAuthContext
    ):
        """Test that mixed valid/invalid UUIDs returns 422."""
        store = DocumentStore(db, user_api_key.project_id)
        crud = DocTransformationJobCrud(db, user_api_key.project_id)
        document = store.put()
        job = crud.create(document.id)

        job_ids_params = f"job_ids={job.id}&job_ids=not-a-uuid"

        response = client.get(
            f"{settings.API_V1_STR}/documents/transformations/?{job_ids_params}",
            headers={"X-API-KEY": user_api_key.key},
        )

        assert response.status_code == 422
        data = response.json()
        assert "Input should be a valid UUID" in data["error"]
        assert "job_ids" in data["error"]

    def test_get_jobs_missing_parameter_422(
        self, client: TestClient, user_api_key: TestAuthContext
    ):
        """Test that missing job_ids parameter returns empty results."""
        response = client.get(
            f"{settings.API_V1_STR}/documents/transformations/",
            headers={"X-API-KEY": user_api_key.key},
        )

        assert response.status_code == 422

    def test_get_jobs_different_project_not_found(
        self,
        client: TestClient,
        db: Session,
        user_api_key: TestAuthContext,
        superuser_api_key: TestAuthContext,
    ):
        """Test that jobs from different projects are not returned."""
        store = DocumentStore(db, user_api_key.project_id)
        crud = DocTransformationJobCrud(db, user_api_key.project_id)
        document = store.put()
        job = crud.create(document.id)

        # Try to access with user from different project (superuser)
        response = client.get(
            f"{settings.API_V1_STR}/documents/transformations/?job_ids={job.id}",
            headers={"X-API-KEY": superuser_api_key.key},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["jobs"]) == 0
        assert len(data["data"]["jobs_not_found"]) == 1
        assert data["data"]["jobs_not_found"][0] == str(job.id)

    def test_get_jobs_with_various_statuses(
        self, client: TestClient, db: Session, user_api_key: TestAuthContext
    ):
        """Test retrieving jobs with different statuses."""
        store = DocumentStore(db, user_api_key.project_id)
        crud = DocTransformationJobCrud(db, user_api_key.project_id)
        documents = store.fill(4)
        jobs = [crud.create(doc.id) for doc in documents]

        crud.update_status(jobs[1].id, TransformationStatus.PROCESSING)
        crud.update_status(
            jobs[2].id,
            TransformationStatus.COMPLETED,
            transformed_document_id=documents[2].id,
        )
        crud.update_status(
            jobs[3].id, TransformationStatus.FAILED, error_message="Test error"
        )

        job_ids_params = "&".join(f"job_ids={job.id}" for job in jobs)

        response = client.get(
            f"{settings.API_V1_STR}/documents/transformations/?{job_ids_params}",
            headers={"X-API-KEY": user_api_key.key},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["jobs"]) == 4

        # Check that all statuses are represented
        statuses = {job["status"] for job in data["data"]["jobs"]}
        expected_statuses = {
            TransformationStatus.PENDING,
            TransformationStatus.PROCESSING,
            TransformationStatus.COMPLETED,
            TransformationStatus.FAILED,
        }
        assert statuses == expected_statuses
