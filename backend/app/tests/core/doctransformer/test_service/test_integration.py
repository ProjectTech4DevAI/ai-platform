"""
Integration tests for document transformation service.
"""
from typing import Tuple
from unittest.mock import patch

import pytest
from fastapi import BackgroundTasks
from moto import mock_aws
from sqlmodel import Session

from app.crud import DocTransformationJobCrud, DocumentCrud
from app.core.doctransform.service import execute_job, start_job
from app.models import (
    Document,
    DocTransformationJob,
    Project,
    TransformationStatus,
    UserProjectOrg,
)
from app.tests.core.doctransformer.test_service.utils import DocTransformTestBase


class TestExecuteJobIntegration(DocTransformTestBase):
    """Integration tests for execute_job function with minimal mocking."""

    @mock_aws
    @pytest.mark.usefixtures("aws_credentials")
    def test_execute_job_end_to_end_workflow(
        self, db: Session, test_document: Tuple[Document, Project]
    ) -> None:
        """Test complete end-to-end workflow from start_job to execute_job."""
        document, project = test_document
        aws = self.setup_aws_s3()
        self.create_s3_document_content(aws, document)

        # Start job using the service
        current_user = UserProjectOrg(
            id=1,
            email="test@example.com",
            project_id=project.id,
            organization_id=project.organization_id,
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
        with patch("app.core.doctransform.service.Session") as mock_session_class:
            mock_session_class.return_value.__enter__.return_value = db
            mock_session_class.return_value.__exit__.return_value = None

            execute_job(
                project_id=project.id,
                job_id=job.id,
                transformer_name="test",
                target_format="markdown",
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
    def test_execute_job_concurrent_jobs(
        self, db: Session, test_document: Tuple[Document, Project]
    ) -> None:
        """Test multiple concurrent job executions don't interfere with each other."""
        document, project = test_document
        aws = self.setup_aws_s3()
        self.create_s3_document_content(aws, document)

        # Create multiple jobs
        job_crud = DocTransformationJobCrud(session=db, project_id=project.id)
        jobs = []
        for i in range(3):
            job = job_crud.create(source_document_id=document.id)
            jobs.append(job)
        db.commit()

        # Execute all jobs
        for job in jobs:
            with patch("app.core.doctransform.service.Session") as mock_session_class:
                mock_session_class.return_value.__enter__.return_value = db
                mock_session_class.return_value.__exit__.return_value = None

                execute_job(
                    project_id=project.id,
                    job_id=job.id,
                    transformer_name="test",
                    target_format="markdown",
                )

        # Verify all jobs completed successfully
        for job in jobs:
            db.refresh(job)
            assert job.status == TransformationStatus.COMPLETED
            assert job.transformed_document_id is not None

    @mock_aws
    @pytest.mark.usefixtures("aws_credentials")
    def test_multiple_format_transformations(
        self, db: Session, test_document: Tuple[Document, Project]
    ) -> None:
        """Test transforming the same document to multiple formats."""
        document, project = test_document
        aws = self.setup_aws_s3()
        self.create_s3_document_content(aws, document)

        formats = ["markdown", "text", "html"]
        jobs = []

        # Create jobs for different formats
        job_crud = DocTransformationJobCrud(session=db, project_id=project.id)
        for target_format in formats:
            job = job_crud.create(source_document_id=document.id)
            jobs.append((job, target_format))
        db.commit()

        # Execute all jobs
        for job, target_format in jobs:
            with patch("app.core.doctransform.service.Session") as mock_session_class:
                mock_session_class.return_value.__enter__.return_value = db
                mock_session_class.return_value.__exit__.return_value = None

                execute_job(
                    project_id=project.id,
                    job_id=job.id,
                    transformer_name="test",
                    target_format=target_format,
                )

        # Verify all jobs completed successfully with correct formats
        document_crud = DocumentCrud(session=db, project_id=project.id)
        for i, (job, target_format) in enumerate(jobs):
            db.refresh(job)
            assert job.status == TransformationStatus.COMPLETED
            assert job.transformed_document_id is not None

            transformed_doc = document_crud.read_one(job.transformed_document_id)
            assert transformed_doc is not None
            # Verify correct file extension based on format
            if target_format == "markdown":
                assert transformed_doc.fname.endswith(".md")
            elif target_format == "text":
                assert transformed_doc.fname.endswith(".txt")
            elif target_format == "html":
                assert transformed_doc.fname.endswith(".html")
