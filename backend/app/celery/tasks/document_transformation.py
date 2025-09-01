import logging
from uuid import UUID
from celery import current_task
from sqlmodel import Session

from app.celery.celery_app import celery_app
from app.core.db import get_engine
from app.core.doctransform import service as transformation_service
from app.crud.doc_transformation_job import DocTransformationJobCrud
from app.models.doc_transformation_job import TransformationStatus

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, queue="long_running")
def transform_document_task(self, job_id: str, transformer_name: str, target_format: str, user_id: int):
    """
    Celery task to handle document transformation.
    """
    job_uuid = UUID(job_id)
    engine = get_engine()
    
    with Session(engine) as session:
        job_crud = DocTransformationJobCrud(session)
        
        try:
            # Update job status to processing and store celery task ID
            job_crud.update_status(
                job_id=job_uuid,
                status=TransformationStatus.PROCESSING,
            )
            
            # Store the celery task ID
            job = job_crud.read_one(job_uuid)
            job.celery_task_id = current_task.request.id
            session.add(job)
            session.commit()
            
            logger.info(f"Starting document transformation job {job_id}")
            
            # Execute the transformation
            transformed_document = transformation_service.execute_job(
                session=session,
                job_id=job_uuid,
                transformer_name=transformer_name,
                target_format=target_format,
                user_id=user_id,
            )
            
            # Update job status to completed
            job_crud.update_status(
                job_id=job_uuid,
                status=TransformationStatus.COMPLETED,
                transformed_document_id=transformed_document.id,
            )
            
            logger.info(f"Document transformation job {job_id} completed successfully")
            return {"status": "completed", "transformed_document_id": str(transformed_document.id)}
            
        except Exception as exc:
            error_message = str(exc)
            logger.error(f"Document transformation job {job_id} failed: {error_message}", exc_info=True)
            
            # Update job status to failed
            job_crud.update_status(
                job_id=job_uuid,
                status=TransformationStatus.FAILED,
                error_message=error_message,
            )
            
            # Re-raise the exception so Celery marks the task as failed
            raise
