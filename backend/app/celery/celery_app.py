import logging
from celery import Celery
from celery.app.control import Control
from celery.signals import worker_ready, worker_shutdown, task_prerun, task_postrun
from kombu import Exchange, Queue

from app.core.config import settings
from app.celery.resource_monitor import resource_monitor

logger = logging.getLogger(__name__)

# Create Celery instance
celery_app = Celery(
    "ai_platform",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.celery.tasks.job_execution",
    ],
)

# Define exchanges and queues with priority
default_exchange = Exchange("default", type="direct")

# Celery configuration
celery_app.conf.update(
    # Queue configuration with priority support
    task_queues=(
        Queue(
            "high_priority",
            exchange=default_exchange,
            routing_key="high",
            queue_arguments={"x-max-priority": 10},
        ),
        Queue(
            "low_priority",
            exchange=default_exchange,
            routing_key="low",
            queue_arguments={"x-max-priority": 1},
        ),
        Queue("cron", exchange=default_exchange, routing_key="cron"),
        Queue("default", exchange=default_exchange, routing_key="default"),
    ),
    # Task routing
    task_routes={
        "app.celery.tasks.job_execution.execute_high_priority_task": {
            "queue": "high_priority",
            "priority": 9,
        },
        "app.celery.tasks.job_execution.execute_low_priority_task": {
            "queue": "low_priority",
            "priority": 1,
        },
        "app.celery.tasks.*_cron_*": {"queue": "cron"},
        "app.celery.tasks.*": {"queue": "default"},
    },
    task_default_queue="default",
    # Enable priority support
    task_inherit_parent_priority=True,
    worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
    # Worker configuration
    worker_concurrency=settings.COMPUTED_CELERY_WORKER_CONCURRENCY,
    worker_max_tasks_per_child=settings.CELERY_WORKER_MAX_TASKS_PER_CHILD,
    worker_max_memory_per_child=settings.CELERY_WORKER_MAX_MEMORY_PER_CHILD,
    # Security
    worker_hijack_root_logger=False,
    worker_log_color=False,
    # Task execution
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_reject_on_worker_lost=True,
    task_ignore_result=False,
    task_acks_late=True,
    # Retry configuration
    task_default_retry_delay=settings.CELERY_TASK_DEFAULT_RETRY_DELAY,
    task_max_retries=settings.CELERY_TASK_MAX_RETRIES,
    # Task configuration
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=settings.CELERY_ENABLE_UTC,
    task_track_started=True,
    task_always_eager=False,
    # Result backend settings
    result_expires=settings.CELERY_RESULT_EXPIRES,
    result_compression="gzip",
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    # Connection settings
    broker_connection_retry_on_startup=True,
    broker_pool_limit=settings.CELERY_BROKER_POOL_LIMIT,
    worker_pool_restarts=True,
)


@worker_ready.connect
def start_resource_monitoring(sender, **kwargs):
    """Start resource monitoring when worker is ready."""
    if not settings.RESOURCE_MONITORING_ENABLED:
        logger.info("Resource monitoring is disabled")
        return

    try:
        # Create Control instance
        control = Control(app=celery_app)

        # Get worker hostname from the sender (consumer)
        worker_hostname = sender.hostname

        # Extract queue names from configuration
        queue_names = [queue.name for queue in celery_app.conf.task_queues]

        # Inject into resource monitor
        resource_monitor.control = control
        resource_monitor.worker_hostname = worker_hostname
        resource_monitor.queue_names = queue_names

        logger.info(
            f"Resource monitor initialized - " f"Queues: {', '.join(queue_names)}"
        )

        # Start monitoring
        resource_monitor.start_monitoring()

    except Exception as e:
        logger.error(f"Failed to start resource monitoring: {e}", exc_info=True)


@worker_shutdown.connect
def stop_resource_monitoring(**kwargs):
    """Stop resource monitoring on worker shutdown."""
    if not settings.RESOURCE_MONITORING_ENABLED:
        return

    resource_monitor.stop_monitoring()


@task_prerun.connect
def track_task_start(**kwargs):
    """Track when a task starts executing."""
    if settings.RESOURCE_MONITORING_ENABLED:
        resource_monitor.increment_active_tasks()


@task_postrun.connect
def track_task_end(**kwargs):
    """Track when a task finishes executing."""
    if settings.RESOURCE_MONITORING_ENABLED:
        resource_monitor.decrement_active_tasks()


# Auto-discover tasks
celery_app.autodiscover_tasks()
