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
from app.core.db import get_engine

logger = logging.getLogger(__name__)


def start_job(
    db: Session,
    current_user: CurrentUser,
    source_document_id: UUID,
    transformer_name: str,
    target_format: str,
) -> UUID:
    """
    Start a document transformation job using Celery (low priority queue).
    Returns the job ID.
    """
    # Extract user_id from current_user
    user_id = current_user.id
    
    # Create the job record and commit immediately
    job_crud = DocTransformationJobCrud(db)
    job = job_crud.create(source_document_id=source_document_id)
    
    # Import here to avoid circular imports
    from app.celery.utils import start_low_priority_job
    
    # Start the low priority Celery task, passing job_id
    task_id = start_low_priority_job(
        function_path="app.core.doctransform.service.execute_job",
        user_id=user_id,
        job_id=str(job.id),
        transformer_name=transformer_name,
        target_format=target_format,
    )
    
    logger.info(f"Started transformation job {job.id} with Celery task {task_id}")
    return job.id


def execute_job(
    user_id: int,
    job_id: str,
    task_id: str,
    task_instance=None,
    transformer_name: str = None,
    target_format: str = None,
) -> dict:
    """
    Execute the actual document transformation.
    Handles all DB updates and error handling.
    Creates its own DB session.
    """
    # Convert job_id to UUID for job lookup
    job_uuid = UUID(job_id)
    
    engine = get_engine()
    with Session(engine) as session:
        job_crud = DocTransformationJobCrud(session)
        job = job_crud.read_one(job_uuid)

        # Update job status to processing and store current celery task ID
        job_crud.update_status(
            job_id=job_uuid,
            status=TransformationStatus.PROCESSING,
        )
        job.celery_task_id = task_id
        session.add(job)
        session.commit()

        # Get the source document
        doc_crud = DocumentCrud(session, user_id)
        source_document = doc_crud.read_one(job.source_document_id)

        logger.info(f"Executing transformation job {job_id} (task {task_id}) for document {source_document.id}")

        # Optional: Update progress using task_instance
        if task_instance:
            task_instance.update_state(
                state="PROGRESS",
                meta={"status": "Processing document transformation..."}
            )

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

            # Update job status to completed
            job_crud.update_status(
                job_id=job_uuid,
                status=TransformationStatus.COMPLETED,
                transformed_document_id=saved_document.id,
            )

            logger.info(f"Transformation job {job_id} (task {task_id}) completed, created document {saved_document.id}")
            return {"status": "completed", "transformed_document_id": str(saved_document.id)}

        except Exception as exc:
            error_message = str(exc)
            logger.error(f"Transformation job {job_id} (task {task_id}) failed: {error_message}", exc_info=True)
            # Update job status to failed
            job_crud.update_status(
                job_id=job_uuid,
                status=TransformationStatus.FAILED,
                error_message=error_message,
            )
            raise
        finally:
            # Clean up temporary files
            Path(temp_file_path).unlink(missing_ok=True)
            if 'result_path' in locals():
                Path(result_path).unlink(missing_ok=True)