import logging
import tempfile
from uuid import UUID, uuid4
from pathlib import Path
from sqlmodel import Session

from app.api.deps import CurrentUser
from app.crud.doc_transformation_job import DocTransformationJobCrud
from app.crud.document import DocumentCrud
from app.models.doc_transformation_job import TransformationStatus
from app.models import Document
from app.core.cloud import AmazonCloudStorage
from app.core.doctransform.registry import resolve_transformer, get_file_format

logger = logging.getLogger(__name__)


def start_job(
    db: Session,
    current_user: CurrentUser,
    source_document_id: UUID,
    transformer_name: str,
    target_format: str,
) -> UUID:
    """
    Start a document transformation job using Celery.
    """
    # Create the job record
    job_crud = DocTransformationJobCrud(db)
    job = job_crud.create(source_document_id=source_document_id)
    
    # Import here to avoid circular imports
    from app.celery.tasks.document_transformation import transform_document_task
    
    # Start the Celery task
    task = transform_document_task.delay(
        job_id=str(job.id),
        transformer_name=transformer_name,
        target_format=target_format,
    )
    
    # Update job with task ID
    job.celery_task_id = task.id
    db.add(job)
    db.commit()
    
    logger.info(f"Started transformation job {job.id} with Celery task {task.id}")
    return job.id


def execute_job(
    session: Session,
    job_id: UUID,
    transformer_name: str,
    target_format: str,
) -> Document:
    """
    Execute the actual document transformation.
    This function is called by the Celery worker.
    """
    job_crud = DocTransformationJobCrud(session)
    job = job_crud.read_one(job_id)
    
    # Get the source document
    doc_crud = DocumentCrud(session, job.source_document.owner_id)
    source_document = doc_crud.read_one(job.source_document_id)
    
    logger.info(f"Executing transformation job {job_id} for document {source_document.id}")
    
    # Create storage client
    from app.models import User
    mock_user = User(id=source_document.owner_id)
    storage = AmazonCloudStorage(mock_user)
    
    # Download source document to temporary file
    with tempfile.NamedTemporaryFile(suffix=f'.{get_file_format(source_document.fname)}', delete=False) as temp_file:
        source_stream = storage.stream(source_document.object_store_url)
        temp_file.write(source_stream.read())
        temp_file_path = temp_file.name
    
    try:
        # Get the transformer and transform the document
        transformer_class = resolve_transformer(
            source_format=get_file_format(source_document.fname),
            target_format=target_format,
            transformer_name=transformer_name,
        )
        
        transformer = transformer_class()
        result_path = transformer.transform(temp_file_path, target_format)
        
        # Upload transformed document to storage
        transformed_id = uuid4()
        transformed_filename = f"{Path(source_document.fname).stem}_transformed.{target_format}"
        
        with open(result_path, 'rb') as f:
            # Create a mock UploadFile-like object
            class MockUploadFile:
                def __init__(self, file, filename, content_type="text/plain"):
                    self.file = file
                    self.filename = filename
                    self.content_type = content_type
            
            mock_upload = MockUploadFile(f, transformed_filename)
            transformed_url = storage.put(mock_upload, Path(str(transformed_id)))
        
        # Create document record
        transformed_document = Document(
            id=transformed_id,
            fname=transformed_filename,
            object_store_url=str(transformed_url),
            owner_id=source_document.owner_id,
            source_document_id=source_document.id,
        )
        
        # Save to database
        saved_document = doc_crud.update(transformed_document)
        
        logger.info(f"Transformation job {job_id} completed, created document {saved_document.id}")
        return saved_document
        
    finally:
        # Clean up temporary files
        Path(temp_file_path).unlink(missing_ok=True)
        if 'result_path' in locals():
            Path(result_path).unlink(missing_ok=True)