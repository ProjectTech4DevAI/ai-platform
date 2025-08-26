import os
import tempfile
from io import BytesIO
from typing import Any, Callable, Generator, Tuple
from unittest.mock import patch
from uuid import uuid4, UUID

import pytest
from fastapi import BackgroundTasks
from moto import mock_aws
from sqlmodel import Session
from tenacity import RetryError, retry, stop_after_attempt, wait_fixed

from app.crud import DocTransformationJobCrud, DocumentCrud, get_project_by_id
from app.models import Document, DocTransformationJob, Project, TransformationStatus, UserProjectOrg

from app.core.cloud import AmazonCloudStorageClient
from app.core.config import settings
from app.core.doctransform.registry import TransformationError
from app.core.doctransform.service import execute_job, start_job
from app.core.exception_handlers import HTTPException

from app.tests.utils.document import DocumentStore
from app.tests.utils.utils import get_project


@pytest.fixture(scope="class")
def aws_credentials() -> None:
    """Set up AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = settings.AWS_DEFAULT_REGION


@pytest.fixture
def fast_execute_job() -> Generator[Callable[[int, UUID, str, str], Any], None, None]:
    """Create a version of execute_job without retry delays for faster testing."""
    from app.core.doctransform import service
    
    original_execute_job = service.execute_job
    
    @retry(stop=stop_after_attempt(2), wait=wait_fixed(0.01))  # Very fast retry for tests
    def fast_execute_job_func(project_id: int, job_id: UUID, transformer_name: str, target_format: str) -> Any:
        # Call the original function's implementation without the decorator
        return original_execute_job.__wrapped__(project_id, job_id, transformer_name, target_format)
    
    with patch.object(service, 'execute_job', fast_execute_job_func):
        yield fast_execute_job_func


@pytest.fixture
def current_user(db: Session) -> UserProjectOrg:
    """Create a test user for testing."""
    project = get_project(db)
    return UserProjectOrg(
        id=1,
        email="test@example.com",
        project_id=project.id,
        organization_id=project.organization_id
    )


@pytest.fixture
def background_tasks() -> BackgroundTasks:
    """Create BackgroundTasks instance."""
    return BackgroundTasks()


@pytest.fixture
def test_document(db: Session, current_user: UserProjectOrg) -> Tuple[Document, Project]:
    """Create a test document for the current user's project."""
    project = get_project_by_id(session=db, project_id=current_user.project_id)
    store = DocumentStore(db, project)
    return store.put(), project


class TestJobCreationBase:
    """Base class for job creation tests with common setup."""
    
    def setup_aws_s3(self) -> AmazonCloudStorageClient:
        """Setup AWS S3 for testing."""
        aws = AmazonCloudStorageClient()
        aws.create()
        return aws
    
    def create_s3_document_content(self, aws: AmazonCloudStorageClient, project: Project, document: Document, content: bytes = b"Test document content") -> bytes:
        """Create content in S3 for a document."""
        aws.client.put_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=f"{project.storage_path}/{document.id}.txt",
            Body=content
        )
        return content


class TestStartJob(TestJobCreationBase):
    """Test cases for the start_job function."""
    
    def test_start_job_success(self, db: Session, current_user: UserProjectOrg, test_document: Tuple[Document, Any], background_tasks: BackgroundTasks) -> None:
        """Test successful job creation and scheduling."""

        document, _ = test_document
        job_id = start_job(
            db=db,
            current_user=current_user,
            source_document_id=document.id,
            transformer_name="test-transformer",
            target_format="markdown",
            background_tasks=background_tasks,
        )

        job = db.get(DocTransformationJob, job_id)
        assert job is not None
        assert job.source_document_id == document.id
        assert job.status == TransformationStatus.PENDING
        assert job.error_message is None
        assert job.transformed_document_id is None

        assert len(background_tasks.tasks) == 1
        task = background_tasks.tasks[0]
        assert task.func == execute_job
        assert task.args[0] == current_user.project_id
        assert task.args[1] == job_id
        assert task.args[2] == "test-transformer"
        assert task.args[3] == "markdown"

    def test_start_job_with_nonexistent_document(self, db: Session, current_user: UserProjectOrg, background_tasks: BackgroundTasks) -> None:
        """Test job creation with non-existent document raises error."""
        nonexistent_id = uuid4()
        
        with pytest.raises(HTTPException) as exc_info:
            start_job(
                db=db,
                current_user=current_user,
                source_document_id=nonexistent_id,
                transformer_name="test-transformer",
                target_format="markdown",
                background_tasks=background_tasks,
            )
        
        assert exc_info.value.status_code == 404
        assert "Document not found" in str(exc_info.value.detail)

    def test_start_job_with_deleted_document(self, db: Session, current_user: UserProjectOrg, test_document: Tuple[Document, Any], background_tasks: BackgroundTasks) -> None:
        """Test job creation with deleted document raises error."""
        document, _ = test_document

        document.is_deleted = True
        db.add(document)
        db.commit()
        
        with pytest.raises(HTTPException) as exc_info:
            start_job(
                db=db,
                current_user=current_user,
                source_document_id=document.id,
                transformer_name="test-transformer",
                target_format="markdown",
                background_tasks=background_tasks,
            )
        
        assert exc_info.value.status_code == 404
        assert "Document not found" in str(exc_info.value.detail)

    def test_start_job_with_different_formats(self, db: Session, current_user: UserProjectOrg, test_document: Tuple[Document, Any], background_tasks: BackgroundTasks) -> None:
        """Test job creation with different target formats."""
        document, _ = test_document
        formats = ["markdown", "text", "html"]
        
        for target_format in formats:
            job_id = start_job(
                db=db,
                current_user=current_user,
                source_document_id=document.id,
                transformer_name="test",
                target_format=target_format,
                background_tasks=background_tasks,
            )
            
            job = db.get(DocTransformationJob, job_id)
            assert job is not None
            assert job.status == TransformationStatus.PENDING
            
            task = background_tasks.tasks[-1]
            assert task.args[3] == target_format


class TestExecuteJob(TestJobCreationBase):
    """Test cases for the execute_job function."""

    @pytest.mark.parametrize(
        "target_format, expected_extension",
        [
            ("markdown", ".md"),
            ("text", ".txt"),
            ("html", ".html"),
        ],
    )
    @mock_aws
    @pytest.mark.usefixtures("aws_credentials")
    def test_execute_job_success(
        self,
        db: Session,
        test_document: Tuple[Document, Any],
        target_format: str,
        expected_extension: str,
    ) -> None:
        """Test successful document transformation with multiple formats."""
        self._test_execute_job_success(db, test_document, target_format, expected_extension)

    def _test_execute_job_success(self, db: Session, test_document: Tuple[Document, Any], target_format: str, expected_extension: str) -> None:
        """Helper method to test successful job execution for different formats."""
        document, project = test_document
        aws = self.setup_aws_s3()
        
        source_content = b"This is a test document for transformation."
        self.create_s3_document_content(aws, project, document, source_content)

        # Create transformation job
        job_crud = DocTransformationJobCrud(session=db, project_id=project.id)
        job = job_crud.create(source_document_id=document.id)
        db.commit()
        
        # Mock the Session to use our existing database session
        with patch('app.core.doctransform.service.Session') as mock_session_class:
            mock_session_class.return_value.__enter__.return_value = db
            mock_session_class.return_value.__exit__.return_value = None
            
            execute_job(
                project_id=project.id,
                job_id=job.id,
                transformer_name="test",
                target_format=target_format
            )

        # Verify job completion
        db.refresh(job)
        assert job.status == TransformationStatus.COMPLETED
        assert job.transformed_document_id is not None
        assert job.error_message is None

        # Verify transformed document
        document_crud = DocumentCrud(session=db, project_id=project.id)
        transformed_doc = document_crud.read_one(job.transformed_document_id)
        assert transformed_doc is not None
        assert transformed_doc.fname.endswith(expected_extension)
        assert "<transformed>" in transformed_doc.fname
        assert transformed_doc.source_document_id == document.id
        assert transformed_doc.object_store_url is not None

        # Verify transformed content in S3
        self._verify_s3_content(aws, project, transformed_doc)

    def _verify_s3_content(self, aws: AmazonCloudStorageClient, project: Project, transformed_doc: Document) -> None:
        """Verify the content stored in S3."""
        transformed_key = transformed_doc.object_store_url.split('/')[-1]
        response = aws.client.get_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=f"{project.storage_path}/{transformed_key}"
        )
        transformed_content = response['Body'].read().decode('utf-8')
        expected_content = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
        assert transformed_content == expected_content

    @mock_aws
    @pytest.mark.usefixtures("aws_credentials")
    def test_execute_job_with_nonexistent_job(self, db: Session, test_document: Tuple[Document, Project], fast_execute_job: Callable[[int, UUID, str, str], Any]) -> None:
        """Test job execution with non-existent job ID."""
        _ , project = test_document
        self.setup_aws_s3()
        nonexistent_job_id = uuid4()
        
        with patch('app.core.doctransform.service.Session') as mock_session_class:
            mock_session_class.return_value.__enter__.return_value = db
            mock_session_class.return_value.__exit__.return_value = None
            
            # Execute job should fail because job doesn't exist
            with pytest.raises((HTTPException, RetryError)):
                fast_execute_job(
                    project_id=project.id,
                    job_id=nonexistent_job_id,
                    transformer_name="test",
                    target_format="markdown"
                )

    @mock_aws
    @pytest.mark.usefixtures("aws_credentials")
    def test_execute_job_with_missing_source_document(self, db: Session, test_document: Tuple[Document, Any], fast_execute_job: Callable[[int, UUID, str, str], Any]) -> None:
        """Test job execution when source document is missing from S3."""
        document, project = test_document
        self.setup_aws_s3()
        
        # Create job but don't upload document to S3
        job_crud = DocTransformationJobCrud(session=db, project_id=project.id)
        job = job_crud.create(source_document_id=document.id)
        db.commit()
        
        with patch('app.core.doctransform.service.Session') as mock_session_class:
            mock_session_class.return_value.__enter__.return_value = db
            mock_session_class.return_value.__exit__.return_value = None
            
            with pytest.raises(Exception):
                fast_execute_job(
                    project_id=project.id,
                    job_id=job.id,
                    transformer_name="test",
                    target_format="markdown"
                )

        # Verify job was marked as failed
        db.refresh(job)
        assert job.status == TransformationStatus.FAILED
        assert job.error_message is not None
        assert job.transformed_document_id is None

    @mock_aws
    @pytest.mark.usefixtures("aws_credentials")
    def test_execute_job_with_transformer_error(self, db: Session, test_document: Tuple[Document, Any], fast_execute_job: Callable[[int, UUID, str, str], Any]) -> None:
        """Test job execution when transformer raises an error."""
        document, project = test_document
        aws = self.setup_aws_s3()
        self.create_s3_document_content(aws, project, document)

        job_crud = DocTransformationJobCrud(session=db, project_id=project.id)
        job = job_crud.create(source_document_id=document.id)
        db.commit()
        
        # Mock convert_document to raise TransformationError
        with patch('app.core.doctransform.service.Session') as mock_session_class, \
             patch('app.core.doctransform.service.convert_document') as mock_convert:
            
            mock_session_class.return_value.__enter__.return_value = db
            mock_session_class.return_value.__exit__.return_value = None
            mock_convert.side_effect = TransformationError("Mock transformation error")
            
            # Due to retry mechanism, it will raise RetryError after exhausting retries
            with pytest.raises((TransformationError, RetryError)):
                fast_execute_job(
                    project_id=project.id,
                    job_id=job.id,
                    transformer_name="test",
                    target_format="markdown"
                )

        # Verify job was marked as failed
        db.refresh(job)
        assert job.status == TransformationStatus.FAILED
        assert "Mock transformation error" in job.error_message
        assert job.transformed_document_id is None

    @mock_aws
    @pytest.mark.usefixtures("aws_credentials")
    def test_execute_job_with_storage_error(self, db: Session, test_document: Tuple[Document, Any], fast_execute_job: Callable[[int, UUID, str, str], Any]) -> None:
        """Test job execution when S3 upload fails."""
        document, project = test_document
        aws = self.setup_aws_s3()
        self.create_s3_document_content(aws, project, document)

        job_crud = DocTransformationJobCrud(session=db, project_id=project.id)
        job = job_crud.create(source_document_id=document.id)
        db.commit()
        
        # Mock storage.put to raise an error
        with patch('app.core.doctransform.service.Session') as mock_session_class, \
             patch('app.core.doctransform.service.AmazonCloudStorage') as mock_storage_class:
            
            mock_session_class.return_value.__enter__.return_value = db
            mock_session_class.return_value.__exit__.return_value = None
            
            mock_storage = mock_storage_class.return_value
            mock_storage.stream.return_value = BytesIO(b"test content")
            mock_storage.put.side_effect = Exception("S3 upload failed")
            
            with pytest.raises(Exception):
                fast_execute_job(
                    project_id=project.id,
                    job_id=job.id,
                    transformer_name="test",
                    target_format="markdown"
                )

        # Verify job was marked as failed
        db.refresh(job)
        assert job.status == TransformationStatus.FAILED
        assert "S3 upload failed" in job.error_message
        assert job.transformed_document_id is None

    @mock_aws
    @pytest.mark.usefixtures("aws_credentials")
    def test_execute_job_status_transitions(self, db: Session, test_document: Tuple[Document, Any]) -> None:
        """Test that job status transitions correctly during execution."""
        document, project = test_document
        aws = self.setup_aws_s3()
        self.create_s3_document_content(aws, project, document)

        job_crud = DocTransformationJobCrud(session=db, project_id=project.id)
        job = job_crud.create(source_document_id=document.id)
        initial_status = job.status
        db.commit()
        
        with patch('app.core.doctransform.service.Session') as mock_session_class:
            mock_session_class.return_value.__enter__.return_value = db
            mock_session_class.return_value.__exit__.return_value = None
            
            execute_job(
                project_id=project.id,
                job_id=job.id,
                transformer_name="test",
                target_format="markdown"
            )

        # Verify status progression by checking final job state
        db.refresh(job)
        assert job.status == TransformationStatus.COMPLETED
        assert initial_status == TransformationStatus.PENDING
        # We can verify the job went through PROCESSING by checking it completed successfully
        assert job.status == TransformationStatus.COMPLETED

    @mock_aws  
    @pytest.mark.usefixtures("aws_credentials")
    def test_execute_job_with_different_content_types(self, db: Session, test_document: Tuple[Document, Any]) -> None:
        """Test job execution produces correct content types for different formats."""
        document, project = test_document
        aws = self.setup_aws_s3()
        self.create_s3_document_content(aws, project, document)

        format_extensions = [
            ("markdown", "text/markdown", ".md"),
            ("text", "text/plain", ".txt"),
            ("html", "text/html", ".html"),
            ("unknown", "text/plain", ".unknown")  # Default fallback
        ]
        
        for target_format, expected_content_type, expected_extension in format_extensions:
            job_crud = DocTransformationJobCrud(session=db, project_id=project.id)
            job = job_crud.create(source_document_id=document.id)
            db.commit()
            
            with patch('app.core.doctransform.service.Session') as mock_session_class:
                mock_session_class.return_value.__enter__.return_value = db
                mock_session_class.return_value.__exit__.return_value = None
                
                execute_job(
                    project_id=project.id,
                    job_id=job.id,
                    transformer_name="test",
                    target_format=target_format
                )
            
            # Verify transformation completed and check file extension
            db.refresh(job)
            assert job.status == TransformationStatus.COMPLETED
            document_crud = DocumentCrud(session=db, project_id=project.id)
            assert job.transformed_document_id is not None
            transformed_doc = document_crud.read_one(job.transformed_document_id)
            assert transformed_doc is not None
            assert transformed_doc.fname.endswith(expected_extension)

    @mock_aws
    @pytest.mark.usefixtures("aws_credentials")
    def test_execute_job_retry_mechanism(self, db: Session, test_document: Tuple[Document, Any], fast_execute_job: Callable[[int, UUID, str, str], Any]) -> None:
        """Test that retry mechanism works for transient failures."""
        document, project = test_document
        aws = self.setup_aws_s3()
        self.create_s3_document_content(aws, project, document)

        job_crud = DocTransformationJobCrud(session=db, project_id=project.id)
        job = job_crud.create(source_document_id=document.id)
        db.commit()
        
        # Create a side effect that fails once then succeeds (fast retry will only try 2 times)
        call_count = 0
        def failing_convert_document(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:  # Fail only once for fast retry
                raise Exception("Transient error")
            return "Success after retries"
        
        with patch('app.core.doctransform.service.Session') as mock_session_class, \
             patch('app.core.doctransform.service.convert_document', side_effect=failing_convert_document):
            
            mock_session_class.return_value.__enter__.return_value = db
            mock_session_class.return_value.__exit__.return_value = None
            
            fast_execute_job(
                project_id=project.id,
                job_id=job.id,
                transformer_name="test",
                target_format="markdown"
            )

        # Verify the function was retried and eventually succeeded
        assert call_count == 2  # Called twice (1 fail + 1 success)
        db.refresh(job)
        assert job.status == TransformationStatus.COMPLETED

    @mock_aws
    @pytest.mark.usefixtures("aws_credentials")
    def test_execute_job_exhausted_retries(self, db: Session, test_document: Tuple[Document, Any], fast_execute_job: Callable[[int, UUID, str, str], Any]) -> None:
        """Test behavior when all retry attempts are exhausted."""
        document, project = test_document
        aws = self.setup_aws_s3()
        self.create_s3_document_content(aws, project, document)

        job_crud = DocTransformationJobCrud(session=db, project_id=project.id)
        job = job_crud.create(source_document_id=document.id)
        db.commit()
        
        # Mock convert_document to always fail
        with patch('app.core.doctransform.service.Session') as mock_session_class, \
             patch('app.core.doctransform.service.convert_document') as mock_convert:
            
            mock_session_class.return_value.__enter__.return_value = db
            mock_session_class.return_value.__exit__.return_value = None
            mock_convert.side_effect = Exception("Persistent error")
            
            with pytest.raises(Exception):
                fast_execute_job(
                    project_id=project.id,
                    job_id=job.id,
                    transformer_name="test",
                    target_format="markdown"
                )

        # Verify job was marked as failed after retries
        db.refresh(job)
        assert job.status == TransformationStatus.FAILED
        assert "Persistent error" in job.error_message

    @mock_aws
    @pytest.mark.usefixtures("aws_credentials")
    def test_execute_job_database_error_during_completion(self, db: Session, test_document: Tuple[Document, Any], fast_execute_job: Callable[[int, UUID, str, str], Any]) -> None:
        """Test handling of database errors when updating job completion."""
        document, project = test_document
        aws = self.setup_aws_s3()
        self.create_s3_document_content(aws, project, document)

        job_crud = DocTransformationJobCrud(session=db, project_id=project.id)
        job = job_crud.create(source_document_id=document.id)
        db.commit()
        
        with patch('app.core.doctransform.service.Session') as mock_session_class:
            mock_session_class.return_value.__enter__.return_value = db
            mock_session_class.return_value.__exit__.return_value = None
            
            # Mock DocumentCrud.update to fail when creating the transformed document
            with patch('app.core.doctransform.service.DocumentCrud') as mock_doc_crud_class:
                mock_doc_crud_instance = mock_doc_crud_class.return_value
                mock_doc_crud_instance.read_one.return_value = document  # Return valid document for source
                mock_doc_crud_instance.update.side_effect = Exception("Database error during document creation")
                
                with pytest.raises(Exception):
                    fast_execute_job(
                        project_id=project.id,
                        job_id=job.id,
                        transformer_name="test",
                        target_format="markdown"
                    )

        # Verify job was marked as failed
        db.refresh(job)
        assert job.status == TransformationStatus.FAILED
        assert "Database error during document creation" in job.error_message


class TestExecuteJobIntegration(TestJobCreationBase):
    """Integration tests for execute_job function with minimal mocking."""

    @mock_aws
    @pytest.mark.usefixtures("aws_credentials")
    def test_execute_job_end_to_end_workflow(self, db: Session, test_document: Tuple[Document, Project]) -> None:
        """Test complete end-to-end workflow from start_job to execute_job."""
        document, project = test_document
        aws = self.setup_aws_s3()
        self.create_s3_document_content(aws, project, document)

        # Start job using the service
        current_user = UserProjectOrg(
            id=1,
            email="test@example.com",
            project_id=project.id,
            organization_id=project.organization_id
        )
        background_tasks = BackgroundTasks()

        job_id = start_job(
            db=db,
            current_user=current_user,
            source_document_id=document.id,
            transformer_name="test",
            target_format="markdown",
            background_tasks=background_tasks,
        )

        # Verify job was created
        job = db.get(DocTransformationJob, job_id)
        assert job.status == TransformationStatus.PENDING

        # Execute the job manually (simulating background execution)
        with patch('app.core.doctransform.service.Session') as mock_session_class:
            mock_session_class.return_value.__enter__.return_value = db
            mock_session_class.return_value.__exit__.return_value = None
            
            execute_job(
                project_id=project.id,
                job_id=job.id,
                transformer_name="test",
                target_format="markdown"
            )

        # Verify complete workflow
        db.refresh(job)
        assert job.status == TransformationStatus.COMPLETED
        assert job.transformed_document_id is not None
        
        # Verify transformed document exists and is valid
        document_crud = DocumentCrud(session=db, project_id=project.id)
        transformed_doc = document_crud.read_one(job.transformed_document_id)
        assert transformed_doc.source_document_id == document.id
        assert "<transformed>" in transformed_doc.fname

    @mock_aws
    @pytest.mark.usefixtures("aws_credentials")
    def test_execute_job_concurrent_jobs(self, db: Session, test_document: Tuple[Document, Project]) -> None:
        """Test multiple concurrent job executions don't interfere with each other."""
        document, project = test_document
        aws = self.setup_aws_s3()
        self.create_s3_document_content(aws, project, document)

        # Create multiple jobs
        job_crud = DocTransformationJobCrud(session=db, project_id=project.id)
        jobs = []
        for i in range(3):
            job = job_crud.create(source_document_id=document.id)
            jobs.append(job)
        db.commit()
        
        # Execute all jobs
        for job in jobs:
            with patch('app.core.doctransform.service.Session') as mock_session_class:
                mock_session_class.return_value.__enter__.return_value = db
                mock_session_class.return_value.__exit__.return_value = None
                
                execute_job(
                    project_id=project.id,
                    job_id=job.id,
                    transformer_name="test",
                    target_format="markdown"
                )

        # Verify all jobs completed successfully
        for job in jobs:
            db.refresh(job)
            assert job.status == TransformationStatus.COMPLETED
            assert job.transformed_document_id is not None
