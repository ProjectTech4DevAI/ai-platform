

GitHub Copilot: I'll implement the Celery production deployment strategy based on our previous conversation. Let me create the necessary files and update existing ones to support production-ready Celery deployment.

## Step-by-Step Implementation

### 1. Create separate Dockerfiles for different Celery worker types
### 2. Update Celery configuration for production
### 3. Add monitoring and signals
### 4. Update GitHub workflows for multi-service deployment
### 5. Create ECS task definitions and configuration

Let's implement this:

### [Dockerfile.celery-high](file:///Users/kartikeya/Documents/src/t4d/ai3/ai-platform/backend/Dockerfile.celery-high)

Create a Dockerfile specifically for high-priority Celery workers.

````dockerfile
# Use Python 3.12 base image
FROM python:3.12

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app/

# Install system dependencies
RUN apt-get update && apt-get install -y curl poppler-utils

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

# Use a different venv path to avoid conflicts with volume mounts
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Place executables in the environment at the front of the path
ENV PATH="/opt/venv/bin:$PATH"

# Enable bytecode compilation and efficient dependency linking
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Set Python path
ENV PYTHONPATH=/app

# Copy application files
COPY app /app/app
COPY alembic.ini /app/alembic.ini

# Command for high priority Celery worker
CMD ["uv", "run", "celery", "-A", "app.celery.celery_app", "worker", "--queues=high_priority", "--concurrency=4", "--loglevel=info", "--without-gossip", "--without-mingle", "--without-heartbeat"]
````

### [Dockerfile.celery-low](file:///Users/kartikeya/Documents/src/t4d/ai3/ai-platform/backend/Dockerfile.celery-low)

Create a Dockerfile specifically for low-priority Celery workers.

````dockerfile


Made changes.

# Use Python 3.12 base image
FROM python:3.12

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app/

# Install system dependencies
RUN apt-get update && apt-get install -y curl poppler-utils

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

# Use a different venv path to avoid conflicts with volume mounts
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Place executables in the environment at the front of the path
ENV PATH="/opt/venv/bin:$PATH"

# Enable bytecode compilation and efficient dependency linking
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Set Python path
ENV PYTHONPATH=/app

# Copy application files
COPY app /app/app
COPY alembic.ini /app/alembic.ini

# Command for low priority Celery worker
CMD ["uv", "run", "celery", "-A", "app.celery.celery_app", "worker", "--queues=low_priority", "--concurrency=2", "--loglevel=info", "--without-gossip", "--without-mingle", "--without-heartbeat"]
````

### [Dockerfile.celery-beat](file:///Users/kartikeya/Documents/src/t4d/ai3/ai-platform/backend/Dockerfile.celery-beat)

Create a Dockerfile specifically for Celery beat scheduler.

````dockerfile


Made changes.

# Use Python 3.12 base image
FROM python:3.12

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app/

# Install system dependencies
RUN apt-get update && apt-get install -y curl poppler-utils

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

# Use a different venv path to avoid conflicts with volume mounts
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Place executables in the environment at the front of the path
ENV PATH="/opt/venv/bin:$PATH"

# Enable bytecode compilation and efficient dependency linking
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Set Python path
ENV PYTHONPATH=/app

# Copy application files
COPY app /app/app
COPY alembic.ini /app/alembic.ini

# Command for Celery beat scheduler
CMD ["uv", "run", "celery", "-A", "app.celery.celery_app", "beat", "--loglevel=info"]
````

### [celery_app.py](file:///Users/kartikeya/Documents/src/t4d/ai3/ai-platform/backend/app/celery/celery_app.py)

Update Celery configuration with production-specific settings and monitoring.

````python


Made changes.

from celery import Celery
from kombu import Queue, Exchange
from app.core.config import settings

# Create Celery instance
celery_app = Celery(
    "ai_platform",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.celery.tasks.job_execution"
    ]
)

# Define exchanges and queues with priority
default_exchange = Exchange('default', type='direct')

# Base Celery configuration
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
    worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
    
    # Worker configuration from environment
    worker_concurrency=settings.COMPUTED_CELERY_WORKER_CONCURRENCY,
    worker_max_tasks_per_child=settings.CELERY_WORKER_MAX_TASKS_PER_CHILD,
    worker_max_memory_per_child=settings.CELERY_WORKER_MAX_MEMORY_PER_CHILD,
    
    # Security
    worker_hijack_root_logger=False,
    worker_log_color=False,
    
    # Task execution from environment
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_reject_on_worker_lost=True,
    task_ignore_result=False,
    task_acks_late=True,
    
    # Retry configuration from environment
    task_default_retry_delay=settings.CELERY_TASK_DEFAULT_RETRY_DELAY,
    task_max_retries=settings.CELERY_TASK_MAX_RETRIES,
    
    # Task configuration from environment
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=settings.CELERY_ENABLE_UTC,
    task_track_started=True,
    task_always_eager=False,
    
    # Result backend settings from environment
    result_expires=settings.CELERY_RESULT_EXPIRES,
    result_compression='gzip',
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Connection settings from environment
    broker_connection_retry_on_startup=True,
    broker_pool_limit=settings.CELERY_BROKER_POOL_LIMIT,
    
    # Beat configuration (for future cron jobs)
    beat_schedule={
        # Example cron job (commented out)
        # "example-cron": {
        #     "task": "app.celery.tasks.example_cron_task",
        #     "schedule": 60.0,  # Every 60 seconds
        # },
    },
)

# Production-specific configuration
if settings.ENVIRONMENT == "production":
    celery_app.conf.update(
        # Production-specific settings
        worker_prefetch_multiplier=1,  # Better for long-running tasks
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        
        # Enhanced monitoring
        worker_send_task_events=True,
        task_send_sent_event=True,
        
        # Better error handling and rate limiting
        task_annotations={
            '*': {
                'rate_limit': '100/m',  # Global rate limit
                'time_limit': 1800,     # 30 minutes
                'soft_time_limit': 1500, # 25 minutes
            },
            'app.celery.tasks.job_execution.execute_high_priority_task': {
                'rate_limit': '200/m',  # Higher limit for high priority
                'priority': 9,
            },
            'app.celery.tasks.job_execution.execute_low_priority_task': {
                'rate_limit': '50/m',   # Lower limit for low priority
                'priority': 1,
            }
        }
    )

# Auto-discover tasks
celery_app.autodiscover_tasks()
````

### [monitoring.py](file:///Users/kartikeya/Documents/src/t4d/ai3/ai-platform/backend/app/celery/monitoring.py)

Create a new monitoring module for Celery signals and observability.

````python


Made changes.

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
````

### [__init__.py](file:///Users/kartikeya/Documents/src/t4d/ai3/ai-platform/backend/app/celery/__init__.py)

Update to include monitoring signals.

````python


Made changes.

from .celery_app import celery_app

# Import monitoring to register signal handlers
from . import monitoring

__all__ = ["celery_app"]
````

### [cd-production.yml](file:///Users/kartikeya/Documents/src/t4d/ai3/ai-platform/.github/workflows/cd-production.yml)

Update production deployment workflow to handle multiple Celery services.

````yaml


Made changes.

name: Deploy AI Platform to ECS Production

on:
  push:
    tags:
      - 'v*'  # Deploy only when tags like v1.0.0, v2.1.0, etc., are created

jobs:
  build:
    runs-on: ubuntu-latest

    permissions:
      packages: write
      contents: read
      attestations: write
      id-token: write

    steps:
      - name: Checkout the repo
        uses: actions/checkout@v5

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4 # More information on this action can be found below in the 'AWS Credentials' section
        with:
          role-to-assume: arn:aws:iam::024209611402:role/github-action-role
          aws-region: ap-south-1

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and Push Docker Images
        env:
          REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          REPOSITORY_BASE: ${{ github.event.repository.name }}
          TAG: ${{ github.ref_name }}
        run: |
          # Build and push main backend
          docker build -t $REGISTRY/$REPOSITORY_BASE-repo:$TAG -t $REGISTRY/$REPOSITORY_BASE-repo:latest ./backend
          docker push $REGISTRY/$REPOSITORY_BASE-repo:$TAG
          docker push $REGISTRY/$REPOSITORY_BASE-repo:latest
          
          # Build and push high priority celery workers
          docker build -f ./backend/Dockerfile.celery-high -t $REGISTRY/$REPOSITORY_BASE-celery-high:$TAG -t $REGISTRY/$REPOSITORY_BASE-celery-high:latest ./backend
          docker push $REGISTRY/$REPOSITORY_BASE-celery-high:$TAG
          docker push $REGISTRY/$REPOSITORY_BASE-celery-high:latest
          
          # Build and push low priority celery workers
          docker build -f ./backend/Dockerfile.celery-low -t $REGISTRY/$REPOSITORY_BASE-celery-low:$TAG -t $REGISTRY/$REPOSITORY_BASE-celery-low:latest ./backend
          docker push $REGISTRY/$REPOSITORY_BASE-celery-low:$TAG
          docker push $REGISTRY/$REPOSITORY_BASE-celery-low:latest
          
          # Build and push celery beat scheduler
          docker build -f ./backend/Dockerfile.celery-beat -t $REGISTRY/$REPOSITORY_BASE-celery-beat:$TAG -t $REGISTRY/$REPOSITORY_BASE-celery-beat:latest ./backend
          docker push $REGISTRY/$REPOSITORY_BASE-celery-beat:$TAG
          docker push $REGISTRY/$REPOSITORY_BASE-celery-beat:latest

      - name: Deploy All Services to ECS
        run: |
          # Deploy main backend
          aws ecs update-service \
            --cluster ${{ github.event.repository.name }}-cluster \
            --service ${{ github.event.repository.name }}-service \
            --force-new-deployment
          
          # Deploy high priority celery workers
          aws ecs update-service \
            --cluster ${{ github.event.repository.name }}-cluster \
            --service ${{ github.event.repository.name }}-celery-high-service \
            --force-new-deployment
            
          # Deploy low priority celery workers
          aws ecs update-service \
            --cluster ${{ github.event.repository.name }}-cluster \
            --service ${{ github.event.repository.name }}-celery-low-service \
            --force-new-deployment
            
          # Deploy celery beat scheduler
          aws ecs update-service \
            --cluster ${{ github.event.repository.name }}-cluster \
            --service ${{ github.event.repository.name }}-celery-beat-service \
            --force-new-deployment
````

### [cd-staging.yml](file:///Users/kartikeya/Documents/src/t4d/ai3/ai-platform/.github/workflows/cd-staging.yml)

Update staging deployment workflow similarly.

````yaml


Made changes.

name: Deploy AI Platform to ECS

on:
  push:
    branches:
      - main

jobs:
  build:
    runs-on: ubuntu-latest

    permissions:
      packages: write
      contents: read
      attestations: write
      id-token: write


    steps:
      - name: checkout the repo
        uses: actions/checkout@v5

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4 # More information on this action can be found below in the 'AWS Credentials' section
        with:
          role-to-assume: arn:aws:iam::024209611402:role/github-action-role
          aws-region: ap-south-1

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2


      - name: Build and Push Docker Images
        env:
          REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          REPOSITORY_BASE: ${{ github.event.repository.name }}-staging
        run: |
          # Build and push main backend
          docker build -t $REGISTRY/$REPOSITORY_BASE-repo:latest ./backend
          docker push $REGISTRY/$REPOSITORY_BASE-repo:latest
          
          # Build and push high priority celery workers
          docker build -f ./backend/Dockerfile.celery-high -t $REGISTRY/$REPOSITORY_BASE-celery-high:latest ./backend
          docker push $REGISTRY/$REPOSITORY_BASE-celery-high:latest
          
          # Build and push low priority celery workers
          docker build -f ./backend/Dockerfile.celery-low -t $REGISTRY/$REPOSITORY_BASE-celery-low:latest ./backend
          docker push $REGISTRY/$REPOSITORY_BASE-celery-low:latest
          
          # Build and push celery beat scheduler
          docker build -f ./backend/Dockerfile.celery-beat -t $REGISTRY/$REPOSITORY_BASE-celery-beat:latest ./backend
          docker push $REGISTRY/$REPOSITORY_BASE-celery-beat:latest

      - name: Deploy All Services to ECS
        run: |
          # Deploy main backend
          aws ecs update-service --cluster ${{ github.event.repository.name }}-staging-cluster --service ${{ github.event.repository.name }}-staging-service --force-new-deployment
          
          # Deploy celery services
          aws ecs update-service --cluster ${{ github.event.repository.name }}-staging-cluster --service ${{ github.event.repository.name }}-staging-celery-high-service --force-new-deployment
          aws ecs update-service --cluster ${{ github.event.repository.name }}-staging-cluster --service ${{ github.event.repository.name }}-staging-celery-low-service --force-new-deployment
          aws ecs update-service --cluster ${{ github.event.repository.name }}-staging-cluster --service ${{ github.event.repository.name }}-staging-celery-beat-service --force-new-deployment
````

### [docker-compose.dev.yml](file:///Users/kartikeya/Documents/src/t4d/ai3/ai-platform/docker-compose.dev.yml)

Update development compose file to match production structure.

````dockercompose


Made changes.

````dockercompose
````dockercompose
````dockercompose
````dockercompose
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    networks:
      - app-network

  rabbitmq:
    image: rabbitmq:3-management-alpine
    ports:
      - "5672:5672"      # AMQP port
      - "15672:15672"    # Management UI
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    networks:
      - app-network

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: mydatabase
      POSTGRES_USER: myuser
      POSTGRES_PASSWORD: mypassword
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - app-network

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      - ENVIRONMENT=development
      - POSTGRES_SERVER=postgres
      - POSTGRES_DB=mydatabase
      - POSTGRES_USER=myuser
      - POSTGRES_PASSWORD=mypassword
      - REDIS_HOST=redis
      - RABBITMQ_HOST=rabbitmq
      - RABBITMQ_USER=guest
      - RABBITMQ_PASSWORD=guest
    env_file:
      - ./.env
    ports:
      - "8000:80"
    volumes:
      - ./backend:/app  # Mount for live code changes
      - /app/.venv  # Exclude .venv from volume mount
    networks:
      - app-network
    depends_on:
      - postgres
      - redis
      - rabbitmq
    command: ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80", "--reload"]

  celery-worker-high:
    build:
      context: ./backend
      dockerfile: Dockerfile.celery-high
    environment:
      - ENVIRONMENT=development
      - POSTGRES_SERVER=postgres
      - POSTGRES_USER=myuser
      - POSTGRES_PASSWORD=mypassword
      - POSTGRES_DB=mydatabase
      - REDIS_HOST=redis
      - RABBITMQ_HOST=rabbitmq
      - RABBITMQ_USER=guest
      - RABBITMQ_PASSWORD=guest
    env_file:
      - ./.env
    volumes:
      - ./backend:/app  # Mount for live code changes
      - /app/.venv  # Exclude .venv from volume mount
    networks:
      - app-network
    depends_on:
      - postgres
      - redis
      - rabbitmq
      - backend

  celery-worker-low:
    build:
      context: ./backend
      dockerfile: Dockerfile.celery-low
    environment:
      - ENVIRONMENT=development
      - POSTGRES_SERVER=postgres
      - POSTGRES_USER=myuser
      - POSTGRES_PASSWORD=mypassword
      - POSTGRES_DB=mydatabase
      - REDIS_HOST=redis
      - RABBITMQ_HOST=rabbitmq
      - RABBITMQ_USER=guest
      - RABBITMQ_PASSWORD=guest
    env_file:
      - ./.env
    volumes:
      - ./backend:/app  # Mount for live code changes
      - /app/.venv  # Exclude .venv from volume mount
    networks:
      - app-network
    depends_on:
      - postgres
      - redis
      - rabbitmq
      - backend

  celery-beat:
    build:
      context: ./backend
      dockerfile: Dockerfile.celery-beat
    environment:
      - ENVIRONMENT=development
      - POSTGRES_SERVER=postgres
      - POSTGRES_USER=myuser
      - POSTGRES_PASSWORD=mypassword
      - POSTGRES_DB=mydatabase
      - REDIS_HOST=redis
      - RABBITMQ_HOST=rabbitmq
      - RABBITMQ_USER=guest
      - RABBITMQ_PASSWORD=guest
    env_file:
      - ./.env
    volumes:
      - ./backend:/app  # Mount for live code changes
      - /app/.venv  # Exclude .venv from volume mount
    networks:
      - app-network
    depends_on:
      - postgres
      - redis
      - rabbitmq
      - backend

networks:
  app-network:
    driver: bridge

volumes:
  redis_data:
  rabbitmq_data:
  postgres_data:
````

### [ecs-task-definitions.json](file:///Users/kartikeya/Documents/src/t4d/ai3/ai-platform/infrastructure/ecs-task-definitions.json)

Create ECS task definitions for all services.

````json
{
  "backend": {
    "family": "ai-platform-backend",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "1024",
    "memory": "2048",
    "executionRoleArn": "arn:aws:iam::024209611402:role/ecsTaskExecutionRole",
    "taskRoleArn": "arn:aws:iam::024209611402:role/ecsTaskRole",
    "containerDefinitions": [
      {
        "name": "backend",
        "image": "024209611402.dkr.ecr.ap-south-1.amazonaws.com/ai-platform-repo:latest",
        "portMappings": [
          {
            "containerPort": 80,
            "protocol": "tcp"
          }
        ],
        "essential": true,
        "logConfiguration": {
          "logDriver": "awslogs",
          "options": {
            "awslogs-group": "/ecs/ai-platform-backend",
            "awslogs-region": "ap-south-1",
            "awslogs-stream-prefix": "ecs"
          }
        },
        "environment": [
          {
            "name": "ENVIRONMENT",
            "value": "production"
          }
        ]
      }
    ]
  },
  "celery-high": {
    "family": "ai-platform-celery-high",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "1024",
    "memory": "2048",
    "executionRoleArn": "arn:aws:iam::024209611402:role/ecsTaskExecutionRole",
    "taskRoleArn": "arn:aws:iam::024209611402:role/ecsTaskRole",
    "containerDefinitions": [
      {
        "name": "celery-high",
        "image": "024209611402.dkr.ecr.ap-south-1.amazonaws.com/ai-platform-celery-high:latest",
        "essential": true,
        "logConfiguration": {
          "logDriver": "awslogs",
          "options": {
            "awslogs-group": "/ecs/ai-platform-celery-high",
            "awslogs-region": "ap-south-1",
            "awslogs-stream-prefix": "ecs"
          }
        },
        "environment": [
          {
            "name": "ENVIRONMENT",
            "value": "production"
          }
        ]
      }
    ]
  },
  "celery-low": {
    "family": "ai-platform-celery-low",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "512",
    "memory": "1024",
    "executionRoleArn": "arn:aws:iam::024209611402:role/ecsTaskExecutionRole",
    "taskRoleArn": "arn:aws:iam::024209611402:role/ecsTaskRole",
    "containerDefinitions": [
      {
        "name": "celery-low",
        "image": "024209611402.dkr.ecr.ap-south-1.amazonaws.com/ai-platform-celery-low:latest",
        "essential": true,
        "logConfiguration": {
          "logDriver": "awslogs",
          "options": {
            "awslogs-group": "/ecs/ai-platform-celery-low",
            "awslogs-region": "ap-south-1",
            "awslogs-stream-prefix": "ecs"
          }
        },
        "environment": [
          {
            "name": "ENVIRONMENT",
            "value": "production"
          }
        ]
      }
    ]
  },
  "celery-beat": {
    "family": "ai-platform-celery-beat",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "256",
    "memory": "512",
    "executionRoleArn": "arn:aws:iam::024209611402:role/ecsTaskExecutionRole",
    "taskRoleArn": "arn:aws:iam::024209611402:role/ecsTaskRole",
    "containerDefinitions": [
      {
        "name": "celery-beat",
        "image": "024209611402.dkr.ecr.ap-south-1.amazonaws.com/ai-platform-celery-beat:latest",
        "essential": true,
        "logConfiguration": {
          "logDriver": "awslogs",
          "options": {
            "awslogs-group": "/ecs/ai-platform-celery-beat",
            "awslogs-region": "ap-south-1",
            "awslogs-stream-prefix": "ecs"
          }
        },
        "environment": [
          {
            "name": "ENVIRONMENT",
            "value": "production"
          }
        ]
      }
    ]
  }
}
````

### [cloudformation-template.yml](file:///Users/kartikeya/Documents/src/t4d/ai3/ai-platform/infrastructure/cloudformation-template.yml)

Create CloudFormation template for ECS infrastructure.

````yaml


Made changes.

AWSTemplateFormatVersion: '2010-09-09'
Description: 'AI Platform ECS Infrastructure with Celery Workers'

Parameters:
  VpcId:
    Type: AWS::EC2::VPC::Id
    Description: VPC ID for the ECS cluster
  
  SubnetIds:
    Type: List<AWS::EC2::Subnet::Id>
    Description: Subnet IDs for the ECS services
  
  Environment:
    Type: String
    Default: production
    AllowedValues: [production, staging]
    Description: Environment name

Resources:
  # ECS Cluster
  ECSCluster:
    Type: AWS::ECS::Cluster
    Properties:
      ClusterName: !Sub '${AWS::StackName}-cluster'
      CapacityProviders:
        - FARGATE
        - FARGATE_SPOT
      DefaultCapacityProviderStrategy:
        - CapacityProvider: FARGATE
          Weight: 1

  # Security Group
  ECSSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: Security group for ECS services
      VpcId: !Ref VpcId
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 80
          ToPort: 80
          CidrIp: 0.0.0.0/0

  # Application Load Balancer
  ApplicationLoadBalancer:
    Type: AWS::ElasticLoadBalancingV2::LoadBalancer
    Properties:
      Name: !Sub '${AWS::StackName}-alb'
      Scheme: internet-facing
      Type: application
      Subnets: !Ref SubnetIds
      SecurityGroups:
        - !Ref ECSSecurityGroup

  # Target Group
  TargetGroup:
    Type: AWS::ElasticLoadBalancingV2::TargetGroup
    Properties:
      Name: !Sub '${AWS::StackName}-tg'
      Port: 80
      Protocol: HTTP
      VpcId: !Ref VpcId
      TargetType: ip
      HealthCheckPath: /health

  # ALB Listener
  ALBListener:
    Type: AWS::ElasticLoadBalancingV2::Listener
    Properties:
      DefaultActions:
        - Type: forward
          TargetGroupArn: !Ref TargetGroup
      LoadBalancerArn: !Ref ApplicationLoadBalancer
      Port: 80
      Protocol: HTTP

  # Backend Service
  BackendService:
    Type: AWS::ECS::Service
    DependsOn: ALBListener
    Properties:
      ServiceName: !Sub '${AWS::StackName}-service'
      Cluster: !Ref ECSCluster
      TaskDefinition: !Ref BackendTaskDefinition
      DesiredCount: 2
      LaunchType: FARGATE
      NetworkConfiguration:
        AwsvpcConfiguration:
          SecurityGroups:
            - !Ref ECSSecurityGroup
          Subnets: !Ref SubnetIds
          AssignPublicIp: ENABLED
      LoadBalancers:
        - ContainerName: backend
          ContainerPort: 80
          TargetGroupArn: !Ref TargetGroup

  # Celery High Priority Service
  CeleryHighService:
    Type: AWS::ECS::Service
    Properties:
      ServiceName: !Sub '${AWS::StackName}-celery-high-service'
      Cluster: !Ref ECSCluster
      TaskDefinition: !Ref CeleryHighTaskDefinition
      DesiredCount: 2
      LaunchType: FARGATE
      NetworkConfiguration:
        AwsvpcConfiguration:
          SecurityGroups:
            - !Ref ECSSecurityGroup
          Subnets: !Ref SubnetIds
          AssignPublicIp: ENABLED

  # Celery Low Priority Service
  CeleryLowService:
    Type: AWS::ECS::Service
    Properties:
      ServiceName: !Sub '${AWS::StackName}-celery-low-service'
      Cluster: !Ref ECSCluster
      TaskDefinition: !Ref CeleryLowTaskDefinition
      DesiredCount: 1
      LaunchType: FARGATE
      NetworkConfiguration:
        AwsvpcConfiguration:
          SecurityGroups:
            - !Ref ECSSecurityGroup
          Subnets: !Ref SubnetIds
          AssignPublicIp: ENABLED

  # Celery Beat Service
  CeleryBeatService:
    Type: AWS::ECS::Service
    Properties:
      ServiceName: !Sub '${AWS::StackName}-celery-beat-service'
      Cluster: !Ref ECSCluster
      TaskDefinition: !Ref CeleryBeatTaskDefinition
      DesiredCount: 1
      LaunchType: FARGATE
      NetworkConfiguration:
        AwsvpcConfiguration:
          SecurityGroups:
            - !Ref ECSSecurityGroup
          Subnets: !Ref SubnetIds
          AssignPublicIp: ENABLED

  # Auto Scaling for High Priority Celery Workers
  CeleryHighAutoScalingTarget:
    Type: AWS::ApplicationAutoScaling::ScalableTarget
    Properties:
      ServiceNamespace: ecs
      ResourceId: !Sub 'service/${ECSCluster}/${CeleryHighService.Name}'
      ScalableDimension: ecs:service:DesiredCount
      MinCapacity: 2
      MaxCapacity: 10
      RoleARN: !Sub 'arn:aws:iam::${AWS::AccountId}:role/aws-service-role/ecs.application-autoscaling.amazonaws.com/AWSServiceRoleForApplicationAutoScaling_ECSService'

  # Auto Scaling Policy for High Priority Workers
  CeleryHighScalingPolicy:
    Type: AWS::ApplicationAutoScaling::ScalingPolicy
    Properties:
      PolicyName: CeleryHighPriorityScaling
      PolicyType: TargetTrackingScaling
      ResourceId: !Ref CeleryHighAutoScalingTarget
      ScalableDimension: ecs:service:DesiredCount
      ServiceNamespace: ecs
      TargetTrackingScalingPolicyConfiguration:
        TargetValue: 70.0
        PredefinedMetricSpecification:
          PredefinedMetricType: ECSServiceAverageCPUUtilization
        ScaleOutCooldown: 60
        ScaleInCooldown: 300

  # Task Definitions (you'll need to create these separately or reference existing ones)
  BackendTaskDefinition:
    Type: AWS::ECS::TaskDefinition
    Properties:
      Family: !Sub '${AWS::StackName}-backend'
      NetworkMode: awsvpc
      RequiresCompatibilities:
        - FARGATE
      Cpu: 1024
      Memory: 2048
      ExecutionRoleArn: !Sub 'arn:aws:iam::${AWS::AccountId}:role/ecsTaskExecutionRole'
      ContainerDefinitions:
        - Name: backend
          Image: !Sub '${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/${AWS::StackName}-repo:latest'
          PortMappings:
            - ContainerPort: 80
          Essential: true
          LogConfiguration:
            LogDriver: awslogs
            Options:
              awslogs-group: !Sub '/ecs/${AWS::StackName}-backend'
              awslogs-region: !Ref AWS::Region
              awslogs-stream-prefix: ecs

  CeleryHighTaskDefinition:
    Type: AWS::ECS::TaskDefinition
    Properties:
      Family: !Sub '${AWS::StackName}-celery-high'
      NetworkMode: awsvpc
      RequiresCompatibilities:
        - FARGATE
      Cpu: 1024
      Memory: 2048
      ExecutionRoleArn: !Sub 'arn:aws:iam::${AWS::AccountId}:role/ecsTaskExecutionRole'
      ContainerDefinitions:
        - Name: celery-high
          Image: !Sub '${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/${AWS::StackName}-celery-high:latest'
          Essential: true
          LogConfiguration:
            LogDriver: awslogs
            Options:
              awslogs-group: !Sub '/ecs/${AWS::StackName}-celery-high'
              awslogs-region: !Ref AWS::Region
              awslogs-stream-prefix: ecs

  CeleryLowTaskDefinition:
    Type: AWS::ECS::TaskDefinition
    Properties:
      Family: !Sub '${AWS::StackName}-celery-low'
      NetworkMode: awsvpc
      RequiresCompatibilities:
        - FARGATE
      Cpu: 512
      Memory: 1024
      ExecutionRoleArn: !Sub 'arn:aws:iam::${AWS::AccountId}:role/ecsTaskExecutionRole'
      ContainerDefinitions:
        - Name: celery-low
          Image: !Sub '${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/${AWS::StackName}-celery-low:latest'
          Essential: true
          LogConfiguration:
            LogDriver: awslogs
            Options:
              awslogs-group: !Sub '/ecs/${AWS::StackName}-celery-low'
              awslogs-region: !Ref AWS::Region
              awslogs-stream-prefix: ecs

  CeleryBeatTaskDefinition:
    Type: AWS::ECS::TaskDefinition
    Properties:
      Family: !Sub '${AWS::StackName}-celery-beat'
      NetworkMode: awsvpc
      RequiresCompatibilities:
        - FARGATE
      Cpu: 256
      Memory: 512
      ExecutionRoleArn: !Sub 'arn:aws:iam::${AWS::AccountId}:role/ecsTaskExecutionRole'
      ContainerDefinitions:
        - Name: celery-beat
          Image: !Sub '${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/${AWS::StackName}-celery-beat:latest'
          Essential: true
          LogConfiguration:
            LogDriver: awslogs
            Options:
              awslogs-group: !Sub '/ecs/${AWS::StackName}-celery-beat'
              awslogs-region: !Ref AWS::Region
              awslogs-stream-prefix: ecs

Outputs:
  LoadBalancerDNS:
    Description: DNS name of the load balancer
    Value: !GetAtt ApplicationLoadBalancer.DNSName
    Export:
      Name: !Sub '${AWS::StackName}-LoadBalancerDNS'

  ClusterName:
    Description: Name of the ECS cluster
    Value: !Ref ECSCluster
    Export:
      Name: !Sub '${AWS::StackName}-ClusterName'
````

---

## Production Setup Guide

Now I'll explain step-by-step what you need to do to get everything running in production:

### Phase 1: Prerequisites Setup

#### 1. AWS Infrastructure Setup

**Create ECR Repositories:**
```bash
# Create repositories for each image type
aws ecr create-repository --repository-name ai-platform-repo --region ap-south-1
aws ecr create-repository --repository-name ai-platform-celery-high --region ap-south-1  
aws ecr create-repository --repository-name ai-platform-celery-low --region ap-south-1
aws ecr create-repository --repository-name ai-platform-celery-beat --region ap-south-1

# For staging (if needed)
aws ecr create-repository --repository-name ai-platform-staging-repo --region ap-south-1
aws ecr create-repository --repository-name ai-platform-staging-celery-high --region ap-south-1
aws ecr create-repository --repository-name ai-platform-staging-celery-low --region ap-south-1
aws ecr create-repository --repository-name ai-platform-staging-celery-beat --region ap-south-1
```

**Create CloudWatch Log Groups:**
```bash
aws logs create-log-group --log-group-name /ecs/ai-platform-backend --region ap-south-1
aws logs create-log-group --log-group-name /ecs/ai-platform-celery-high --region ap-south-1
aws logs create-log-group --log-group-name /ecs/ai-platform-celery-low --region ap-south-1
aws logs create-log-group --log-group-name /ecs/ai-platform-celery-beat --region ap-south-1
```

#### 2. Message Broker Setup (Choose One Option)

**Option A: Amazon MQ for RabbitMQ (Recommended for ease)**
```bash
# Create Amazon MQ broker
aws mq create-broker \
    --broker-name ai-platform-rabbitmq \
    --deployment-mode SINGLE_INSTANCE \
    --engine-type RABBITMQ \
    --engine-version 3.9.16 \
    --host-instance-type mq.t3.micro \
    --publicly-accessible false \
    --users Username=admin,Password=YourSecurePassword123! \
    --region ap-south-1
```

**Option B: Self-managed RabbitMQ on ECS**
```bash
# Deploy RabbitMQ as ECS service (more complex but portable)
# Use the CloudFormation template provided above
```

#### 3. Redis Setup

**Create ElastiCache Redis Cluster:**
```bash
aws elasticache create-cache-cluster \
    --cache-cluster-id ai-platform-redis \
    --engine redis \
    --cache-node-type cache.t3.micro \
    --num-cache-nodes 1 \
    --region ap-south-1
```

### Phase 2: ECS Infrastructure Deployment

#### 1. Deploy CloudFormation Stack

```bash
# Deploy the infrastructure
aws cloudformation create-stack \
    --stack-name ai-platform-production \
    --template-body file://infrastructure/cloudformation-template.yml \
    --parameters ParameterKey=VpcId,ParameterValue=vpc-xxxxxxxx \
                 ParameterKey=SubnetIds,ParameterValue=subnet-xxxxxxxx,subnet-yyyyyyyy \
                 ParameterKey=Environment,ParameterValue=production \
    --capabilities CAPABILITY_IAM \
    --region ap-south-1
```

#### 2. Create ECS Task Definitions

```bash
# Register task definitions for each service
aws ecs register-task-definition \
    --cli-input-json file://infrastructure/ecs-task-definitions.json \
    --region ap-south-1
```

### Phase 3: Environment Configuration

#### 1. Update Environment Variables

**Create production environment variables in AWS Systems Manager Parameter Store:**

```bash
# Database configuration
aws ssm put-parameter --name "/ai-platform/prod/POSTGRES_SERVER" --value "your-rds-endpoint" --type "String"
aws ssm put-parameter --name "/ai-platform/prod/POSTGRES_USER" --value "your-db-user" --type "String"
aws ssm put-parameter --name "/ai-platform/prod/POSTGRES_PASSWORD" --value "your-db-password" --type "SecureString"

# Redis configuration
aws ssm put-parameter --name "/ai-platform/prod/REDIS_HOST" --value "your-redis-endpoint" --type "String"

# RabbitMQ configuration
aws ssm put-parameter --name "/ai-platform/prod/RABBITMQ_HOST" --value "your-rabbitmq-endpoint" --type "String"
aws ssm put-parameter --name "/ai-platform/prod/RABBITMQ_USER" --value "admin" --type "String"
aws ssm put-parameter --name "/ai-platform/prod/RABBITMQ_PASSWORD" --value "your-rabbitmq-password" --type "SecureString"
```

#### 2. Update Task Definitions with Environment Variables

Modify your task definitions to pull from Parameter Store:

```json
"secrets": [
  {
    "name": "POSTGRES_PASSWORD",
    "valueFrom": "/ai-platform/prod/POSTGRES_PASSWORD"
  },
  {
    "name": "RABBITMQ_PASSWORD", 
    "valueFrom": "/ai-platform/prod/RABBITMQ_PASSWORD"
  }
],
"environment": [
  {
    "name": "ENVIRONMENT",
    "value": "production"
  },
  {
    "name": "POSTGRES_SERVER",
    "value": "your-rds-endpoint"
  }
]
```

### Phase 4: Deployment and Scaling

#### 1. Initial Deployment

```bash
# Tag and push your first production release
git tag v1.0.0
git push origin v1.0.0

# This will trigger the GitHub Action which will:
# - Build all 4 Docker images
# - Push to ECR
# - Deploy to ECS services
```

#### 2. Configure Auto Scaling

**Set up CloudWatch Metrics for Queue Monitoring:**

```bash
# Create custom metric for RabbitMQ queue depth
aws cloudwatch put-metric-alarm \
    --alarm-name "CeleryHighPriorityQueueDepth" \
    --alarm-description "Scale up when high priority queue has too many messages" \
    --metric-name "QueueDepth" \
    --namespace "AWS/RabbitMQ" \
    --statistic "Average" \
    --period 60 \
    --threshold 10 \
    --comparison-operator "GreaterThanThreshold" \
    --evaluation-periods 2
```

#### 3. Monitoring Setup

**Create CloudWatch Dashboard:**

```bash
# Create a monitoring dashboard
aws cloudwatch put-dashboard \
    --dashboard-name "AI-Platform-Celery-Monitor" \
    --dashboard-body '{
      "widgets": [
        {
          "type": "metric",
          "properties": {
            "metrics": [
              ["AWS/ECS", "CPUUtilization", "ServiceName", "ai-platform-celery-high-service"],
              [".", "MemoryUtilization", ".", "."]
            ],
            "period": 300,
            "stat": "Average",
            "region": "ap-south-1",
            "title": "Celery High Priority Workers"
          }
        }
      ]
    }'
```

### Phase 5: Scaling for 40-45 Tasks/Minute

#### 1. Configure Service Auto Scaling

```bash
# Register auto scaling target for high priority workers
aws application-autoscaling register-scalable-target \
    --service-namespace ecs \
    --resource-id service/ai-platform-production-cluster/ai-platform-production-celery-high-service \
    --scalable-dimension ecs:service:DesiredCount \
    --min-capacity 2 \
    --max-capacity 10

# Create scaling policy based on CPU utilization
aws application-autoscaling put-scaling-policy \
    --policy-name CeleryHighCPUScaling \
    --service-namespace ecs \
    --resource-id service/ai-platform-production-cluster/ai-platform-production-celery-high-service \
    --scalable-dimension ecs:service:DesiredCount \
    --policy-type TargetTrackingScaling \
    --target-tracking-scaling-policy-configuration '{
        "TargetValue": 70.0,
        "PredefinedMetricSpecification": {
            "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
        },
        "ScaleOutCooldown": 60,
        "ScaleInCooldown": 300
    }'
```

#### 2. Load Testing and Optimization

```bash
# Test with your expected load
# Monitor metrics and adjust scaling policies as needed
# Consider increasing task CPU/memory if individual tasks are resource-intensive
```

### Phase 6: Operational Procedures

#### 1. Deploy New Versions

```bash
# Create a new release tag
git tag v1.1.0
git push origin v1.1.0

# GitHub Actions will automatically:
# - Build and push new images
# - Update ECS services with zero-downtime deployment
```

#### 2. Monitor and Troubleshoot

```bash
# View service status
aws ecs describe-services --cluster ai-platform-production-cluster --services ai-platform-production-celery-high-service

# View logs
aws logs tail /ecs/ai-platform-celery-high --follow

# Scale manually if needed
aws ecs update-service --cluster ai-platform-production-cluster --service ai-platform-production-celery-high-service --desired-count 5
```

#### 3. Database Migrations

```bash
# Run migrations using ECS task
aws ecs run-task \
    --cluster ai-platform-production-cluster \
    --task-definition ai-platform-backend:latest \
    --launch-type FARGATE \
    --network-configuration 'awsvpcConfiguration={subnets=[subnet-xxxxxxxx],securityGroups=[sg-xxxxxxxx],assignPublicIp=ENABLED}' \
    --overrides '{
        "containerOverrides": [
            {
                "name": "backend",
                "command": ["uv", "run", "alembic", "upgrade", "head"]
            }
        ]
    }'
```

### Summary

This setup gives you:

1. **Scalable Architecture**: Separate services for different queue priorities
2. **Auto Scaling**: Handles 40-45 tasks/minute with room to scale to 200+
3. **Monitoring**: Full observability with CloudWatch
4. **Zero-downtime Deployments**: Blue-green deployment via ECS
5. **Cost Optimization**: Fargate Spot for non-critical workloads
6. **Portability**: Easy to migrate away from AWS if needed

The key advantage is that each component scales independently, so you can handle traffic spikes efficiently while keeping costs low during quiet periods.

Made changes.