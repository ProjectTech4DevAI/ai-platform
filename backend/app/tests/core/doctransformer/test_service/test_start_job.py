"""
Tests for the start_job function in document transformation service.
"""
from typing import Any, Tuple
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session

from app.core.doctransform.service import execute_job, start_job
from app.core.exception_handlers import HTTPException
from app.models import Document, DocTransformationJob, Project, TransformationStatus, UserProjectOrg
from app.tests.core.doctransformer.test_service.base import DocTransformTestBase, TestDataProvider


class TestStartJob(DocTransformTestBase):
    """Test cases for the start_job function."""
    
    def test_start_job_success(
        self, 
        db: Session, 
        current_user: UserProjectOrg, 
        test_document: Tuple[Document, Project], 
        background_tasks: BackgroundTasks
    ) -> None:
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

    def test_start_job_with_nonexistent_document(
        self, 
        db: Session, 
        current_user: UserProjectOrg, 
        background_tasks: BackgroundTasks
    ) -> None:
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

    def test_start_job_with_deleted_document(
        self, 
        db: Session, 
        current_user: UserProjectOrg, 
        test_document: Tuple[Document, Project], 
        background_tasks: BackgroundTasks
    ) -> None:
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

    def test_start_job_with_different_formats(
        self, 
        db: Session, 
        current_user: UserProjectOrg, 
        test_document: Tuple[Document, Project], 
        background_tasks: BackgroundTasks
    ) -> None:
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

    @pytest.mark.parametrize("transformer_name", TestDataProvider.get_test_transformer_names())
    def test_start_job_with_different_transformers(
        self, 
        db: Session, 
        current_user: UserProjectOrg, 
        test_document: Tuple[Document, Project], 
        background_tasks: BackgroundTasks,
        transformer_name: str
    ) -> None:
        """Test job creation with different transformer names."""
        document, _ = test_document
        
        job_id = start_job(
            db=db,
            current_user=current_user,
            source_document_id=document.id,
            transformer_name=transformer_name,
            target_format="markdown",
            background_tasks=background_tasks,
        )
        
        job = db.get(DocTransformationJob, job_id)
        assert job is not None
        assert job.status == TransformationStatus.PENDING
        
        task = background_tasks.tasks[-1]
        assert task.args[2] == transformer_name
