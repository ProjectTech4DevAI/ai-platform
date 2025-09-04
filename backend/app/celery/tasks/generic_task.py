import logging
import importlib
from uuid import UUID
from typing import Any, Dict
from celery import current_task

from app.celery.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, queue="long_running")
def execute_job_task(self, job_id: str, function_path: str, user_id: int, **kwargs):
    """
    Generic Celery task to execute any job function.
    
    Args:
        job_id: UUID of the job
        function_path: Import path to the execute_job function (e.g., "app.core.doctransform.service.execute_job")
        user_id: ID of the user executing the job
        **kwargs: Additional arguments to pass to the execute_job function
    """
    job_uuid = UUID(job_id)
    celery_task_id = current_task.request.id

    try:
        # Dynamically import and resolve the function
        module_path, function_name = function_path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        execute_function = getattr(module, function_name)
        
        logger.info(f"Executing job {job_id} using function {function_path}")
        
        # Execute the business logic function with all parameters
        result = execute_function(
            job_id=job_uuid,
            user_id=user_id,
            celery_task_id=celery_task_id,
            **kwargs
        )
        
        logger.info(f"Job {job_id} completed successfully")
        return result
        
    except Exception as exc:
        logger.error(f"Job {job_id} failed: {exc}", exc_info=True)
        raise
