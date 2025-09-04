from celery import Celery
import os
from kombu import Queue, Exchange
from app.core.config import settings

# Create Celery instance
celery_app = Celery(
    "ai_platform",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.celery.tasks.job_execution",
        "app.celery.tasks.example_tasks"
    ]
)

# Define exchanges and queues with priority
default_exchange = Exchange('default', type='direct')

# Celery configuration
celery_app.conf.update(
    # Queue configuration with priority support
    task_queues=(
        Queue('high_priority', exchange=default_exchange, routing_key='high',
              queue_arguments={'x-max-priority': 10}),
        Queue('low_priority', exchange=default_exchange, routing_key='low',
              queue_arguments={'x-max-priority': 1}),
        Queue('cron', exchange=default_exchange, routing_key='cron'),
        Queue('default', exchange=default_exchange, routing_key='default'),
    ),
    
    # Task routing
    task_routes={
        'app.celery.tasks.job_execution.execute_high_priority_task': {'queue': 'high_priority', 'priority': 9},
        'app.celery.tasks.job_execution.execute_low_priority_task': {'queue': 'low_priority', 'priority': 1},
        'app.celery.tasks.*_cron_*': {'queue': 'cron'},
        'app.celery.tasks.*': {'queue': 'default'},
    },
    
    task_default_queue="default",
    
    # Enable priority support
    task_inherit_parent_priority=True,
    worker_prefetch_multiplier=1,  # Required for priority queues
    
    # Worker configuration
    worker_concurrency=os.cpu_count(),
    worker_max_tasks_per_child=1000,
    
    # Security
    worker_hijack_root_logger=False,
    worker_log_color=False,
    
    # Task execution
    task_soft_time_limit=300,          # Soft timeout (5 min)
    task_time_limit=600,               # Hard timeout (10 min)
    task_reject_on_worker_lost=True,   # Reject tasks if worker dies
    task_ignore_result=False,          # Store task results
    task_acks_late=True,               # Acknowledge task after completion
    
    # Retry configuration
    task_default_retry_delay=60,       # Default retry delay
    task_max_retries=3,                # Max retries per task
    
    # Task configuration
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_always_eager=False,
    
    # Result backend settings
    result_expires=3600,               # Results expire after 1 hour
    result_compression='gzip',         # Compress results
    
    # Monitoring
    worker_send_task_events=True,      # Enable task events
    task_send_sent_event=True,         # Send task sent events
    
    # Memory management
    worker_max_memory_per_child=200000,  # 200MB per worker
    
    # Connection settings
    broker_connection_retry_on_startup=True,
    broker_pool_limit=10,
    
    # Beat configuration (for future cron jobs)
    beat_schedule={
        # Example cron job (commented out)
        # "example-cron": {
        #     "task": "app.celery.tasks.example_cron_task",
        #     "schedule": 60.0,  # Every 60 seconds
        # },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks()
