import logging
from uuid import UUID
from celery import current_task

from app.celery.celery_app import celery_app
from app.core.doctransform import service as transformation_service

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, queue="long_running")
def transform_document_task(self, job_id: str, transformer_name: str, target_format: str, user_id: int):
    """
    Celery task to handle document transformation.
    Only passes arguments and celery_task_id to the business logic.
    """
    job_uuid = UUID(job_id)
    celery_task_id = current_task.request.id

    try:
        # All business logic and DB updates are handled in execute_job
        result = transformation_service.execute_job(
            job_id=job_uuid,
            transformer_name=transformer_name,
            target_format=target_format,
            user_id=user_id,
            celery_task_id=celery_task_id,
        )
        logger.info(f"Document transformation job {job_id} completed successfully")
        return result
    except Exception as exc:
        logger.error(f"Document transformation job {job_id} failed: {exc}", exc_info=True)
        raise
