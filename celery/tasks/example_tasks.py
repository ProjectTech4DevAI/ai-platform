import time
import logging
from celery import current_task
from ..celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, queue="long_running")
def long_running_task(self, duration: int = 30, task_name: str = "default"):
    """
    Example long-running task that can be run in parallel.
    
    Args:
        duration: How long the task should run (in seconds)
        task_name: Name of the task for logging
    """
    try:
        logger.info(f"Starting long running task: {task_name} (duration: {duration}s)")
        
        # Update task state
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 0,
                "total": duration,
                "status": f"Starting {task_name}..."
            }
        )
        
        # Simulate long-running work with progress updates
        for i in range(duration):
            time.sleep(1)
            
            # Update progress
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": i + 1,
                    "total": duration,
                    "status": f"Processing {task_name}... {i+1}/{duration}"
                }
            )
            
            logger.info(f"Task {task_name} progress: {i+1}/{duration}")
        
        result = {
            "task_name": task_name,
            "duration": duration,
            "status": "completed",
            "message": f"Task {task_name} completed successfully"
        }
        
        logger.info(f"Completed long running task: {task_name}")
        return result
        
    except Exception as exc:
        logger.error(f"Task {task_name} failed: {str(exc)}")
        self.update_state(
            state="FAILURE",
            meta={
                "error": str(exc),
                "task_name": task_name
            }
        )
        raise

@celery_app.task(queue="cron")
def example_cron_task():
    """
    Example cron task for future periodic job functionality.
    """
    logger.info("Running example cron task")
    
    # Simulate some periodic work
    result = {
        "timestamp": time.time(),
        "status": "completed",
        "message": "Cron task executed successfully"
    }
    
    logger.info("Completed example cron task")
    return result

@celery_app.task(bind=True, queue="default")
def parallel_processing_task(self, data_chunks: list, process_func: str = "default"):
    """
    Example task for parallel processing of data chunks.
    
    Args:
        data_chunks: List of data chunks to process
        process_func: Type of processing function to use
    """
    try:
        logger.info(f"Starting parallel processing task with {len(data_chunks)} chunks")
        
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 0,
                "total": len(data_chunks),
                "status": "Starting parallel processing..."
            }
        )
        
        results = []
        for i, chunk in enumerate(data_chunks):
            # Simulate processing each chunk
            processed_chunk = f"processed_{chunk}_{process_func}"
            results.append(processed_chunk)
            
            # Update progress
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": i + 1,
                    "total": len(data_chunks),
                    "status": f"Processing chunk {i+1}/{len(data_chunks)}"
                }
            )
            
            time.sleep(0.5)  # Simulate processing time
        
        result = {
            "processed_chunks": results,
            "total_chunks": len(data_chunks),
            "status": "completed"
        }
        
        logger.info(f"Completed parallel processing task")
        return result
        
    except Exception as exc:
        logger.error(f"Parallel processing task failed: {str(exc)}")
        self.update_state(
            state="FAILURE",
            meta={"error": str(exc)}
        )
        raise
