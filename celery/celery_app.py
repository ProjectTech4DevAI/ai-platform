import os
from celery import Celery
from kombu import Queue

# Import settings from the main app
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.core.config import settings

# Create Celery instance
celery_app = Celery(
    "ai_platform_worker",
    broker=f"redis://localhost:6379/0",
    backend=f"redis://localhost:6379/0",
    include=["celery.tasks"]
)

# Configure Celery
celery_app.conf.update(
    # Task routing
    task_routes={
        "celery.tasks.*": {"queue": "default"},
    },
    
    # Queue configuration
    task_default_queue="default",
    task_queues=(
        Queue("default", routing_key="default"),
        Queue("long_running", routing_key="long_running"),
        Queue("cron", routing_key="cron"),
    ),
    
    # Worker configuration
    worker_concurrency=os.cpu_count(),  # Use all available cores
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    
    # Task configuration
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Result backend configuration
    result_expires=3600,  # 1 hour
    
    # Beat configuration (for future cron jobs)
    beat_schedule={
        # Example cron job (commented out)
        # "example-cron": {
        #     "task": "celery.tasks.example_cron_task",
        #     "schedule": 60.0,  # Every 60 seconds
        # },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks()
