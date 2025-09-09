"""
Celery monitoring and signal handlers for production observability.
"""
import logging
import time
from celery.signals import (
    task_prerun, task_postrun, task_failure, task_retry,
    worker_ready, worker_shutdown
)

logger = logging.getLogger(__name__)


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Log when a task starts."""
    logger.info(f"Task {task.name}[{task_id}] started")
    # Store start time for duration calculation
    task.request.start_time = time.time()


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwds):
    """Log when a task completes."""
    duration = None
    if hasattr(task.request, 'start_time'):
        duration = time.time() - task.request.start_time
    
    logger.info(f"Task {task.name}[{task_id}] completed with state: {state}" + 
                (f" in {duration:.2f}s" if duration else ""))


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
    """Log when a task fails."""
    logger.error(f"Task {sender.name}[{task_id}] failed: {exception}")
    logger.debug(f"Task {sender.name}[{task_id}] traceback: {traceback}")


@task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, einfo=None, **kwds):
    """Log when a task is retried."""
    logger.warning(f"Task {sender.name}[{task_id}] retry: {reason}")


@worker_ready.connect
def worker_ready_handler(sender=None, **kwds):
    """Log when worker is ready."""
    logger.info(f"Celery worker {sender.hostname} is ready")


@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwds):
    """Log when worker shuts down."""
    logger.info(f"Celery worker {sender.hostname} is shutting down")
