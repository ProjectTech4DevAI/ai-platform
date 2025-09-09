import pytest
from sqlmodel import Session
from app.crud.doc_transformation_job import DocTransformationJobCrud
from app.models import TransformationStatus
from app.core.exception_handlers import HTTPException
from app.tests.utils.document import DocumentStore
from app.tests.utils.utils import get_project, SequentialUuidGenerator
from app.tests.utils.test_data import create_test_project


@pytest.fixture
def store(db: Session):
    project = get_project(db)
    return DocumentStore(db, project.id)


@pytest.fixture
def crud(db: Session, store: DocumentStore):
    return DocTransformationJobCrud(db, store.project.id)


class TestDocTransformationJobCrudCreate:
    def test_can_create_job_with_valid_document(
        self, db: Session, store: DocumentStore, crud: DocTransformationJobCrud
    ):
        """Test creating a transformation job with a valid source document."""
        document = store.put()

        job = crud.create(document.id)

        assert job.id is not None
        assert job.source_document_id == document.id
        assert job.status == TransformationStatus.PENDING
        assert job.error_message is None
        assert job.transformed_document_id is None
        assert job.created_at is not None
        assert job.updated_at is not None

    def test_cannot_create_job_with_invalid_document(
        self, db: Session, store: DocumentStore, crud: DocTransformationJobCrud
    ):
        """Test that creating a job with non-existent document raises an error."""
        invalid_id = next(SequentialUuidGenerator())

        with pytest.raises(HTTPException) as exc_info:
            crud.create(invalid_id)

        assert exc_info.value.status_code == 404
        assert "Document not found" in str(exc_info.value.detail)

    def test_cannot_create_job_with_deleted_document(
        self, db: Session, store: DocumentStore, crud: DocTransformationJobCrud
    ):
        """Test that creating a job with a deleted document raises an error."""
        document = store.put()
        # Mark document as deleted
        document.is_deleted = True
        db.add(document)
        db.commit()

        with pytest.raises(HTTPException) as exc_info:
            crud.create(document.id)

        assert exc_info.value.status_code == 404
        assert "Document not found" in str(exc_info.value.detail)


class TestDocTransformationJobCrudReadOne:
    def test_can_read_existing_job(
        self, db: Session, store: DocumentStore, crud: DocTransformationJobCrud
    ):
        """Test reading an existing transformation job."""
        document = store.put()
        job = crud.create(document.id)

        result = crud.read_one(job.id)

        assert result.id == job.id
        assert result.source_document_id == document.id
        assert result.status == TransformationStatus.PENDING

    def test_cannot_read_nonexistent_job(
        self, db: Session, store: DocumentStore, crud: DocTransformationJobCrud
    ):
        """Test that reading a non-existent job raises an error."""
        invalid_id = next(SequentialUuidGenerator())

        with pytest.raises(HTTPException) as exc_info:
            crud.read_one(invalid_id)

        assert exc_info.value.status_code == 404
        assert "Transformation job not found" in str(exc_info.value.detail)

    def test_cannot_read_job_with_deleted_document(
        self, db: Session, store: DocumentStore, crud: DocTransformationJobCrud
    ):
        """Test that reading a job whose source document is deleted raises an error."""
        document = store.put()
        job = crud.create(document.id)

        # Mark document as deleted
        document.is_deleted = True
        db.add(document)
        db.commit()

        with pytest.raises(HTTPException) as exc_info:
            crud.read_one(job.id)

        assert exc_info.value.status_code == 404
        assert "Transformation job not found" in str(exc_info.value.detail)

    def test_cannot_read_job_from_different_project(
        self, db: Session, store: DocumentStore
    ):
        """Test that reading a job from a different project raises an error."""
        document = store.put()
        job_crud = DocTransformationJobCrud(db, store.project.id)
        job = job_crud.create(document.id)

        # Try to read from different project
        other_project = create_test_project(db)
        other_crud = DocTransformationJobCrud(db, other_project.id)

        with pytest.raises(HTTPException) as exc_info:
            other_crud.read_one(job.id)

        assert exc_info.value.status_code == 404
        assert "Transformation job not found" in str(exc_info.value.detail)


class TestDocTransformationJobCrudReadEach:
    def test_can_read_multiple_existing_jobs(
        self, db: Session, store: DocumentStore, crud: DocTransformationJobCrud
    ):
        """Test reading multiple existing transformation jobs."""
        documents = store.fill(3)
        jobs = [crud.create(doc.id) for doc in documents]
        job_ids = {job.id for job in jobs}

        results = crud.read_each(job_ids)

        assert len(results) == 3
        result_ids = {job.id for job in results}
        assert result_ids == job_ids

    def test_read_partial_existing_jobs(
        self, db: Session, store: DocumentStore, crud: DocTransformationJobCrud
    ):
        """Test reading a mix of existing and non-existing jobs."""
        documents = store.fill(2)
        jobs = [crud.create(doc.id) for doc in documents]
        job_ids = {job.id for job in jobs}
        job_ids.add(next(SequentialUuidGenerator()))  # Add non-existent ID

        results = crud.read_each(job_ids)

        assert len(results) == 2  # Only existing jobs returned
        result_ids = {job.id for job in results}
        assert result_ids == {job.id for job in jobs}

    def test_read_empty_job_set(
        self, db: Session, store: DocumentStore, crud: DocTransformationJobCrud
    ):
        """Test reading an empty set of job IDs."""
        results = crud.read_each(set())

        assert len(results) == 0

    def test_cannot_read_jobs_from_different_project(
        self, db: Session, store: DocumentStore
    ):
        """Test that jobs from different projects are not returned."""
        document = store.put()
        job_crud = DocTransformationJobCrud(db, store.project.id)
        job = job_crud.create(document.id)

        # Try to read from different project
        other_project = get_project(db, name="Dalgo")
        other_crud = DocTransformationJobCrud(db, other_project.id)

        results = other_crud.read_each({job.id})

        assert len(results) == 0


class TestDocTransformationJobCrudUpdateStatus:
    def test_can_update_status_to_processing(
        self, db: Session, store: DocumentStore, crud: DocTransformationJobCrud
    ):
        """Test updating job status to processing."""
        document = store.put()
        job = crud.create(document.id)

        updated_job = crud.update_status(job.id, TransformationStatus.PROCESSING)

        assert updated_job.id == job.id
        assert updated_job.status == TransformationStatus.PROCESSING
        assert updated_job.updated_at >= job.updated_at

    def test_can_update_status_to_completed_with_result(
        self, db: Session, store: DocumentStore, crud: DocTransformationJobCrud
    ):
        """Test updating job status to completed with transformed document."""
        source_document = store.put()
        transformed_document = store.put()
        job = crud.create(source_document.id)

        updated_job = crud.update_status(
            job.id,
            TransformationStatus.COMPLETED,
            transformed_document_id=transformed_document.id,
        )

        assert updated_job.status == TransformationStatus.COMPLETED
        assert updated_job.transformed_document_id == transformed_document.id
        assert updated_job.error_message is None

    def test_can_update_status_to_failed_with_error(
        self, db: Session, store: DocumentStore, crud: DocTransformationJobCrud
    ):
        """Test updating job status to failed with error message."""
        document = store.put()
        job = crud.create(document.id)
        error_msg = "Transformation failed due to invalid format"

        updated_job = crud.update_status(
            job.id, TransformationStatus.FAILED, error_message=error_msg
        )

        assert updated_job.status == TransformationStatus.FAILED
        assert updated_job.error_message == error_msg
        assert updated_job.transformed_document_id is None

    def test_cannot_update_nonexistent_job(
        self, db: Session, store: DocumentStore, crud: DocTransformationJobCrud
    ):
        """Test that updating a non-existent job raises an error."""
        invalid_id = next(SequentialUuidGenerator())

        with pytest.raises(HTTPException) as exc_info:
            crud.update_status(invalid_id, TransformationStatus.PROCESSING)

        assert exc_info.value.status_code == 404
        assert "Transformation job not found" in str(exc_info.value.detail)

    def test_update_preserves_existing_fields(
        self, db: Session, store: DocumentStore, crud: DocTransformationJobCrud
    ):
        """Test that updating status preserves other fields when not specified."""
        document = store.put()
        job = crud.create(document.id)

        # First update with error message
        crud.update_status(
            job.id, TransformationStatus.FAILED, error_message="Initial error"
        )

        # Second update without error message - should preserve it
        updated_job = crud.update_status(job.id, TransformationStatus.PROCESSING)

        assert updated_job.status == TransformationStatus.PROCESSING
        assert updated_job.error_message == "Initial error"  # Should be preserved
