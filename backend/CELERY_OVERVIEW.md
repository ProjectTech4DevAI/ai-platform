# Celery Infrastructure Overview

This document provides a comprehensive overview of the Celery-based asynchronous task processing system in the Kaapi AI platform.

## Architecture Overview

The Celery infrastructure enables asynchronous job execution with priority-based queue management, using:
- **Message Broker**: RabbitMQ (for task distribution)
- **Result Backend**: Redis (for task result storage)
- **Task Execution**: Distributed workers with configurable concurrency
- **Scheduling**: Celery Beat for cron jobs

## File Structure

```
app/celery/
├── __init__.py              # Package initialization, exports celery_app
├── celery_app.py            # Main Celery application configuration
├── worker.py                # Worker management and startup script
├── beat.py                  # Beat scheduler for cron jobs
├── utils.py                 # High-level utilities for job scheduling
└── tasks/
    ├── __init__.py          # Task package initialization
    └── job_execution.py     # Generic job execution tasks
```

---

## Core Components

### 1. `celery_app.py` - Celery Application Configuration

**Purpose**: Creates and configures the main Celery application instance with queue management, routing, and worker settings.

#### Key Features:

**Queue Architecture** (lines 22-37):
- **`high_priority`**: For urgent operations (max priority: 10)
  - Examples: Real-time LLM API calls, critical document transformations
- **`low_priority`**: For background operations (max priority: 1)
  - Examples: Batch processing, cleanup tasks
- **`cron`**: For scheduled/periodic tasks
- **`default`**: For general tasks without specific priority

**Task Routing** (lines 39-50):
Automatically routes tasks based on function names:
```python
{
    "execute_high_priority_task": -> high_priority queue (priority 9)
    "execute_low_priority_task":  -> low_priority queue (priority 1)
    "*_cron_*":                   -> cron queue
    "*":                          -> default queue
}
```

**Worker Configuration** (lines 54-58):
- `worker_concurrency`: Number of worker processes (from settings or CPU count)
- `worker_prefetch_multiplier`: Tasks per worker to prefetch
- `worker_max_tasks_per_child`: Restart worker after N tasks (memory management)
- `worker_max_memory_per_child`: Restart worker if memory exceeds limit

**Task Execution Settings** (lines 63-70):
- `task_soft_time_limit`: Graceful timeout warning
- `task_time_limit`: Hard timeout (kills task)
- `task_reject_on_worker_lost`: Re-queue tasks if worker crashes
- `task_acks_late`: Acknowledge task only after completion
- `task_default_retry_delay`: Wait time between retries
- `task_max_retries`: Maximum retry attempts

**Serialization & Storage** (lines 72-80):
- JSON serialization for cross-language compatibility
- Gzip compression for results
- Result expiration time
- Timezone handling (UTC)

**Monitoring** (lines 82-84):
- `worker_send_task_events`: Enable event broadcasting
- `task_send_sent_event`: Track task lifecycle
- Enables Flower monitoring dashboard

---

### 2. `tasks/job_execution.py` - Generic Job Execution

**Purpose**: Provides two priority-based Celery tasks that can dynamically execute any job function via import path.

#### Functions:

**`execute_high_priority_task()`** (lines 11-33):
- Decorated with `@celery_app.task(bind=True, queue="high_priority")`
- Receives function import path and dynamically executes it
- Used for time-sensitive operations

**`execute_low_priority_task()`** (lines 36-58):
- Decorated with `@celery_app.task(bind=True, queue="low_priority")`
- Same functionality as high priority but for background jobs

**`_execute_job_internal()`** (lines 61-117):
- **Dynamic Import** (lines 88-91): Uses `importlib` to load the execute function at runtime
  ```python
  module_path, function_name = "app.services.llm.jobs.execute_job".rsplit(".", 1)
  module = importlib.import_module("app.services.llm.jobs")
  execute_function = getattr(module, "execute_job")
  ```
- **Correlation ID** (line 84): Sets trace_id in context for distributed tracing
- **Standardized Parameters**: All execute functions receive:
  - `project_id`: Project context
  - `job_id`: Database job record ID
  - `task_id`: Celery task ID
  - `task_instance`: For progress updates and retries
  - `**kwargs`: Additional custom parameters

#### Design Pattern: Generic Task Wrapper

This approach allows any service to schedule Celery tasks without creating service-specific Celery tasks:

```python
# Instead of creating a dedicated Celery task for each service:
@celery_app.task
def process_llm_request(...):
    # LLM-specific logic

@celery_app.task
def transform_document(...):
    # Document transform logic

# We have ONE generic task that can execute ANY function:
@celery_app.task
def execute_high_priority_task(function_path, ...):
    # Dynamically import and execute function_path
```

**Benefits**:
- Single point of configuration for all async jobs
- Consistent error handling and logging
- Easy to add new async operations without modifying Celery code

---

### 3. `utils.py` - High-Level Job Scheduling API

**Purpose**: Provides simple utility functions for business logic to schedule jobs without knowing Celery internals.

#### Functions:

**`start_high_priority_job()`** (lines 18-43):
```python
def start_high_priority_job(
    function_path: str,    # "app.services.llm.jobs.execute_job"
    project_id: int,       # 123
    job_id: str,           # "uuid-of-job"
    trace_id: str,         # "correlation-id"
    **kwargs               # Additional args passed to execute_job
) -> str:                  # Returns Celery task_id
```

**Example Usage**:
```python
# From app/services/llm/jobs.py:start_job()
task_id = start_high_priority_job(
    function_path="app.services.llm.jobs.execute_job",
    project_id=project_id,
    job_id=str(job.id),
    trace_id=trace_id,
    request_data=request.model_dump(mode="json"),
    organization_id=organization_id,
)
```

**`start_low_priority_job()`** (lines 46-71):
- Identical to high priority but uses the low priority queue

**`get_task_status()`** (lines 74-90):
- Returns task status, result, and metadata from Redis backend
- Uses `AsyncResult` to query task state

**`revoke_task()`** (lines 93-110):
- Cancels a running or pending task
- Optional `terminate=True` to forcefully kill running task

---

### 4. `worker.py` - Worker Management Script

**Purpose**: Command-line script to start Celery workers with custom configuration.

#### `start_worker()` Function (lines 13-40):

**Parameters**:
- `queues`: Comma-separated queue names to consume (default: all queues)
- `concurrency`: Worker process count (default: from settings or CPU count)
- `loglevel`: Log verbosity

**Worker Options** (lines 34-40):
- `without_gossip=True`: Disables worker-to-worker communication (reduces network overhead)
- `without_mingle=True`: Disables startup synchronization with other workers (faster startup)

**Command-Line Interface** (lines 43-66):
```bash
# Start worker consuming all queues
python -m app.celery.worker

# Consume only high priority tasks
python -m app.celery.worker --queues high_priority

# Custom concurrency
python -m app.celery.worker --concurrency 8 --loglevel debug
```

---

### 5. `beat.py` - Scheduler for Periodic Tasks

**Purpose**: Starts the Celery Beat scheduler for cron-like periodic tasks.

#### `start_beat()` Function (lines 11-20):

**Functionality**:
- Reads periodic task schedule from configuration
- Sends tasks to the `cron` queue at scheduled intervals
- Typically runs as a separate process from workers

**Command-Line Interface** (lines 23-35):
```bash
# Start beat scheduler
python -m app.celery.beat

# With custom log level
python -m app.celery.beat --loglevel debug
```

**Note**: While the scheduler infrastructure is in place, no periodic tasks are currently defined in the codebase.

---

## Data Flow: End-to-End Example

Let's trace an LLM API call through the system:

### 1. **API Request** (`app/api/routes/llm.py`)
```python
# User makes API request
POST /api/v1/llm/call
{
    "config": {"id": 123, "version": 1},
    "query": "What is AI?",
    "callback_url": "https://example.com/webhook"
}
```

### 2. **Job Creation** (`app/services/llm/jobs.py:start_job()`)
```python
# Create database job record
job = JobCrud.create(job_type=JobType.LLM_API, status=PENDING)

# Schedule Celery task
task_id = start_high_priority_job(
    function_path="app.services.llm.jobs.execute_job",
    project_id=123,
    job_id=str(job.id),
    trace_id="abc-123",
    request_data={...}
)
# Returns immediately with job.id
```

### 3. **Task Scheduling** (`app/celery/utils.py:start_high_priority_job()`)
```python
# Sends task to RabbitMQ high_priority queue
task = execute_high_priority_task.delay(
    function_path="app.services.llm.jobs.execute_job",
    project_id=123,
    job_id="uuid",
    trace_id="abc-123",
    request_data={...}
)
```

### 4. **Worker Picks Up Task** (`app/celery/tasks/job_execution.py`)
```python
# Worker dequeues task from RabbitMQ
@celery_app.task(bind=True, queue="high_priority")
def execute_high_priority_task(self, function_path, ...):
    # Dynamically imports: app.services.llm.jobs.execute_job
    module = importlib.import_module("app.services.llm.jobs")
    execute_function = getattr(module, "execute_job")

    # Executes the function
    result = execute_function(project_id, job_id, task_id, ...)
```

### 5. **Job Execution** (`app/services/llm/jobs.py:execute_job()`)
```python
# Update job status to PROCESSING
JobCrud.update(job_id, status=PROCESSING)

# Resolve config from database
config_blob = resolve_config_blob(config_id, version)

# Get LLM provider (OpenAI, Anthropic, etc.)
provider = get_llm_provider(provider_type)

# Execute LLM call
response, error = provider.execute(config_blob, query)

# Send callback webhook
send_callback(callback_url, response)

# Update job status to SUCCESS
JobCrud.update(job_id, status=SUCCESS)

# Return result (stored in Redis)
return APIResponse.success_response(data=response)
```

### 6. **Result Retrieval**
```python
# Client can poll for job status
GET /api/v1/jobs/{job_id}

# Or receive webhook callback
POST https://example.com/webhook
{
    "success": true,
    "data": {
        "response": {...},
        "usage": {...}
    }
}
```

---

## Priority Queue System

### How It Works:

1. **Queue Declaration** (RabbitMQ):
   - Each queue has `x-max-priority` argument
   - `high_priority`: max priority 10
   - `low_priority`: max priority 1

2. **Task Routing**:
   - Tasks are routed to queues based on function name
   - Each task gets a priority number (9 for high, 1 for low)

3. **Worker Consumption**:
   - Workers can consume multiple queues
   - Within a queue, higher priority tasks execute first
   - Tasks with same priority use FIFO order

### Use Cases:

**High Priority**:
- Real-time user-facing operations
- LLM API calls
- Time-sensitive document processing
- Operations with user waiting

**Low Priority**:
- Background data processing
- Cleanup operations
- Non-urgent batch jobs
- Analytics and reporting

---

## Configuration Parameters

All settings come from `app/core/config.py` and can be set via environment variables:

### Infrastructure
- `RABBITMQ_URL`: RabbitMQ connection string
- `REDIS_URL`: Redis connection string

### Worker Settings
- `CELERY_WORKER_CONCURRENCY`: Number of worker processes
- `COMPUTED_CELERY_WORKER_CONCURRENCY`: Auto-calculated concurrency
- `CELERY_WORKER_PREFETCH_MULTIPLIER`: Tasks prefetched per worker
- `CELERY_WORKER_MAX_TASKS_PER_CHILD`: Restart worker after N tasks
- `CELERY_WORKER_MAX_MEMORY_PER_CHILD`: Restart worker at memory limit

### Task Settings
- `CELERY_TASK_SOFT_TIME_LIMIT`: Soft timeout in seconds
- `CELERY_TASK_TIME_LIMIT`: Hard timeout in seconds
- `CELERY_TASK_DEFAULT_RETRY_DELAY`: Retry delay in seconds
- `CELERY_TASK_MAX_RETRIES`: Maximum retry attempts

### Result Backend
- `CELERY_RESULT_EXPIRES`: Result expiration time in seconds

### Timezone
- `CELERY_TIMEZONE`: Timezone for scheduled tasks
- `CELERY_ENABLE_UTC`: Enable UTC normalization

### Connection
- `CELERY_BROKER_POOL_LIMIT`: Max broker connections

---

## Error Handling & Reliability

### 1. **Task Acknowledgement** (`task_acks_late=True`)
- Task acknowledged only AFTER successful completion
- If worker crashes, task is re-queued automatically

### 2. **Worker Lost Recovery** (`task_reject_on_worker_lost=True`)
- Tasks are returned to queue if worker dies unexpectedly

### 3. **Retry Configuration**
- Automatic retries with exponential backoff
- Configurable max retries and delay

### 4. **Timeout Protection**
- Soft timeout: Sends `SoftTimeLimitExceeded` exception
- Hard timeout: Kills task process with `SIGKILL`

### 5. **Memory Management**
- Workers restart after N tasks (prevents memory leaks)
- Workers restart if memory exceeds threshold

### 6. **Correlation IDs**
- `trace_id` propagated through entire request lifecycle
- Enables distributed tracing and debugging

---

## Monitoring & Observability

### 1. **Task Events** (`worker_send_task_events=True`)
- Workers broadcast task lifecycle events
- Can be consumed by Flower dashboard

### 2. **Task Tracking** (`task_track_started=True`)
- Track when tasks start execution
- Distinguish between PENDING and STARTED states

### 3. **Logging**
- Structured logging with correlation IDs
- Task start/completion/failure logged
- Integration with application-wide logging

### 4. **Result Storage**
- All task results stored in Redis
- Compressed with gzip
- Expiration for automatic cleanup

### Recommended Tools:
- **Flower**: Real-time Celery monitoring dashboard
- **RabbitMQ Management**: Queue depth, message rates
- **Redis Commander**: Result backend inspection

---

## Best Practices

### 1. **Job Scheduling Pattern**
Always create a database job record BEFORE scheduling Celery task:
```python
# CORRECT
job = JobCrud.create(job_type=JobType.LLM_API)
task_id = start_high_priority_job(..., job_id=str(job.id))

# WRONG - no job tracking
task_id = start_high_priority_job(...)  # No job_id!
```

### 2. **Error Handling**
Execute functions should handle errors and update job status:
```python
try:
    result = do_work()
    JobCrud.update(job_id, status=SUCCESS)
    return success_response(result)
except Exception as e:
    JobCrud.update(job_id, status=FAILED, error=str(e))
    return error_response(str(e))
```

### 3. **Idempotency**
Tasks should be idempotent (safe to retry):
```python
# CORRECT - check if already processed
if job.status == SUCCESS:
    return existing_result

# WRONG - duplicate processing on retry
upload_file(...)  # Uploads again on retry!
```

### 4. **Use Callbacks for Long Operations**
Don't make users wait for async operations:
```python
# API endpoint returns immediately with job_id
return {"job_id": job.id, "status": "pending"}

# Worker sends result to callback_url when done
send_callback(callback_url, result)
```

### 5. **Priority Selection**
- Use high priority for user-facing operations
- Use low priority for background maintenance
- Don't overuse high priority (defeats the purpose)

---

## Common Operations

### Starting Workers (Development)
```bash
# Single worker, all queues
python -m app.celery.worker

# Multiple workers (production)
python -m app.celery.worker --concurrency 4 --queues high_priority,default &
python -m app.celery.worker --concurrency 2 --queues low_priority &
```

### Starting Beat Scheduler
```bash
python -m app.celery.beat
```

### Monitoring with Flower
```bash
celery -A app.celery.celery_app flower --port=5555
# Access: http://localhost:5555
```

### Checking Task Status
```python
from app.celery.utils import get_task_status

status = get_task_status(task_id)
# Returns: {"task_id": "...", "status": "SUCCESS", "result": {...}}
```

### Canceling Tasks
```python
from app.celery.utils import revoke_task

# Prevent pending task from starting
revoke_task(task_id, terminate=False)

# Kill running task
revoke_task(task_id, terminate=True)
```

---

## Integration Points

### 1. **LLM Service** (`app/services/llm/`)
- Uses high priority queue for real-time API calls
- Dynamic config resolution from database
- Webhook callbacks for async results

### 2. **Document Transform Service** (`app/services/doctransform/`)
- Likely uses high priority for document processing
- File uploads/downloads from cloud storage

### 3. **Future Services**
Any new service can integrate by:
1. Creating an `execute_job()` function with standard signature
2. Calling `start_high_priority_job()` or `start_low_priority_job()`
3. Handling results via callback or job status polling

---

## Summary

The Celery infrastructure provides:

- **Scalability**: Horizontal scaling via worker processes
- **Reliability**: Task acknowledgement, retries, and recovery
- **Prioritization**: Separate queues for urgent vs background work
- **Flexibility**: Generic task execution via dynamic imports
- **Observability**: Event streaming, logging, and monitoring
- **Simplicity**: Clean API via `utils.py` for business logic

The architecture follows the **separation of concerns** principle:
- Business logic in `app/services/`
- Task execution in `app/celery/tasks/`
- Infrastructure config in `app/celery/celery_app.py`
- Simple API in `app/celery/utils.py`

This design makes it easy to add new async operations without modifying core Celery infrastructure.
