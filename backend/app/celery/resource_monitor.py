# app/celery/resource_monitor.py
import logging
import psutil
import threading
import time
from typing import List

from app.core.config import settings
from celery.app.control import Control

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """
    Monitor system resources and control task consumption.
    Uses Celery Control API to pause/resume queue consumption.
    """

    def __init__(
        self,
        cpu_threshold: float = settings.CPU_THRESHOLD_PERCENT,
        memory_threshold: float = settings.MEMORY_THRESHOLD_PERCENT,
        check_interval: int = settings.RESOURCE_CHECK_INTERVAL,
    ):
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self.check_interval = check_interval
        self.is_paused = False
        self.active_tasks = 0
        self.lock = threading.Lock()
        self._should_stop = False
        
        # Will be set by signal
        self.control: Control = None
        self.worker_hostname = None
        self.queue_names: List[str] = []

    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        return psutil.cpu_percent(interval=1)

    def get_memory_usage(self) -> float:
        """Get current memory usage percentage."""
        return psutil.virtual_memory().percent

    def should_pause(self, cpu: float, memory: float) -> bool:
        """Determine if worker should pause based on thresholds."""
        return cpu > self.cpu_threshold or memory > self.memory_threshold

    def pause_consumer(self):
        """Stop consuming tasks from all queues."""
        if not self.control or not self.worker_hostname:
            logger.error("Control or worker hostname not initialized")
            return

        if not self.queue_names:
            logger.error("No queue names configured")
            return

        try:
            # Cancel consumption for each queue
            for queue_name in self.queue_names:
                self.control.cancel_consumer(
                    queue=queue_name,
                    destination=[self.worker_hostname]
                )
                logger.info(f"Cancelled consumer for queue: {queue_name}")
            
            self.is_paused = True
            logger.warning(
                f"🛑 Worker PAUSED - stopped consuming from queues: {', '.join(self.queue_names)}"
            )
        except Exception as e:
            logger.error(f"Error pausing consumer: {e}", exc_info=True)

    def resume_consumer(self):
        """Resume consuming tasks from all queues."""
        if not self.control or not self.worker_hostname:
            logger.error("Control or worker hostname not initialized")
            return

        if not self.queue_names:
            logger.error("No queue names configured")
            return

        try:
            # Add consumers back for each queue
            for queue_name in self.queue_names:
                self.control.add_consumer(
                    queue=queue_name,
                    destination=[self.worker_hostname]
                )
                logger.info(f"Added consumer for queue: {queue_name}")
            
            self.is_paused = False
            logger.info(
                f"✅ Worker RESUMED - started consuming from queues: {', '.join(self.queue_names)}"
            )
        except Exception as e:
            logger.error(f"Error resuming consumer: {e}", exc_info=True)

    def monitor_loop(self):
        """Main monitoring loop - runs in separate thread."""
        logger.info(
            f"🔍 Resource monitoring started - "
            f"CPU threshold: {self.cpu_threshold}%, "
            f"Memory threshold: {self.memory_threshold}%, "
            f"Check interval: {self.check_interval}s, "
            f"Monitoring queues: {', '.join(self.queue_names)}"
        )

        while not self._should_stop:
            try:
                cpu = self.get_cpu_usage()
                memory = self.get_memory_usage()
                should_pause_now = self.should_pause(cpu, memory)
                # Remove this line later
                logger.info("Memmory Usage: {:.2f}%, CPU Usage: {:.2f}%".format(memory, cpu))
                with self.lock:
                    # Pause if resources exceeded and not already paused
                    if should_pause_now and not self.is_paused:
                        logger.warning(
                            f"⚠️  Resource threshold exceeded! "
                            f"CPU: {cpu:.1f}% (limit: {self.cpu_threshold}%), "
                            f"Memory: {memory:.1f}% (limit: {self.memory_threshold}%), "
                            f"Active tasks: {self.active_tasks}. "
                            f"Pausing task consumption..."
                        )
                        self.pause_consumer()

                    # Resume if resources OK and currently paused
                    elif not should_pause_now and self.is_paused:
                        logger.info(
                            f"✓ Resources within limits - "
                            f"CPU: {cpu:.1f}%, Memory: {memory:.1f}%, "
                            f"Active tasks: {self.active_tasks}. "
                            f"Resuming task consumption..."
                        )
                        self.resume_consumer()

                    elif not self.is_paused:
                        logger.debug(
                            f"📊 Status - CPU: {cpu:.1f}%, Memory: {memory:.1f}%, "
                            f"Active tasks: {self.active_tasks}, Paused: {self.is_paused}"
                        )

            except Exception as e:
                logger.error(f"Error in resource monitor loop: {e}", exc_info=True)

            time.sleep(self.check_interval)

        logger.info("Resource monitoring loop ended")

    def  start_monitoring(self):
        """Start the monitoring thread."""
        if not self.control or not self.worker_hostname:
            logger.error("Cannot start monitoring: control or worker hostname not set")
            return

        if not self.queue_names:
            logger.error("Cannot start monitoring: no queues configured")
            return

        self._should_stop = False
        monitor_thread = threading.Thread(
            target=self.monitor_loop,
            daemon=True,
            name="ResourceMonitor"
        )
        monitor_thread.start()
        logger.info("✨ Resource monitoring thread started")

    def stop_monitoring(self):
        """Stop the monitoring thread."""
        logger.info("Stopping resource monitoring...")
        self._should_stop = True
        
        # Ensure consumer is consuming on shutdown
        with self.lock:
            if self.is_paused:
                logger.info("Resuming consumer before shutdown...")
                self.resume_consumer()

    def increment_active_tasks(self):
        """Track task start."""
        with self.lock:
            self.active_tasks += 1

    def decrement_active_tasks(self):
        """Track task end."""
        with self.lock:
            self.active_tasks = max(0, self.active_tasks - 1)


resource_monitor = ResourceMonitor()