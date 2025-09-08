import logging
import importlib
from typing import Any, Dict
from celery import current_task

from app.celery.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, queue="high_priority")
def execute_high_priority_task(self, function_path: str, project_id: int, job_id: str, **kwargs):
    """
    High priority Celery task to execute any job function.
    Use this for urgent operations that need immediate processing.
    
    Args:
        function_path: Import path to the execute_job function (e.g., "app.core.doctransform.service.execute_job")
        project_id: ID of the project executing the job
        job_id: ID of the job (should already exist in database)
        **kwargs: Additional arguments to pass to the execute_job function
    """
    return _execute_job_internal(self, function_path, project_id, job_id, "high_priority", **kwargs)


@celery_app.task(bind=True, queue="low_priority")
def execute_low_priority_task(self, function_path: str, project_id: int, job_id: str, **kwargs):
    """
    Low priority Celery task to execute any job function.
    Use this for background operations that can wait.
    
    Args:
        function_path: Import path to the execute_job function (e.g., "app.core.doctransform.service.execute_job")
        project_id: ID of the project executing the job
        job_id: ID of the job (should already exist in database)
        **kwargs: Additional arguments to pass to the execute_job function
    """
    return _execute_job_internal(self, function_path, project_id, job_id, "low_priority", **kwargs)


def _execute_job_internal(task_instance, function_path: str, project_id: int, job_id: str, priority: str, **kwargs):
    """
    Internal function to execute job logic for both priority levels.
    
    Args:
        task_instance: Celery task instance (for progress updates, retries, etc.)
        function_path: Import path to the execute_job function
        project_id: ID of the project executing the job
        job_id: ID of the job (should already exist in database)
        priority: Priority level ("high_priority" or "low_priority")
        **kwargs: Additional arguments to pass to the execute_job function
    """
    task_id = current_task.request.id

    try:
        # Dynamically import and resolve the function
        module_path, function_name = function_path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        execute_function = getattr(module, function_name)
        
        logger.info(f"Executing {priority} job {job_id} (task {task_id}) using function {function_path}")
        
        # Execute the business logic function with standardized parameters
        result = execute_function(
            project_id=project_id,
            job_id=job_id,
            task_id=task_id,
            task_instance=task_instance,  # For progress updates, retries if needed
            **kwargs
        )
        
        logger.info(f"{priority.capitalize()} job {job_id} (task {task_id}) completed successfully")
        return result
        
    except Exception as exc:
        logger.error(f"{priority.capitalize()} job {job_id} (task {task_id}) failed: {exc}", exc_info=True)
        raise

