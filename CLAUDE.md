# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

Kaapi is an AI platform built with FastAPI and PostgreSQL, containerized with Docker. It provides AI capabilities including OpenAI assistants, fine-tuning, document processing, and collection management.

## Key Commands

### Development

```bash
# Activate virtual environment
source .venv/bin/activate

# Start development server with auto-reload
fastapi run --reload app/main.py

# Run pre-commit hooks
uv run pre-commit run --all-files

# Generate database migration
alembic revision --autogenerate -m 'Description'

# Seed database with test data
uv run python -m app.seed_data.seed_data
```

### Testing

Tests use `.env.test` for environment-specific configuration.

```bash
# Run test suite
uv run bash scripts/tests-start.sh
```

## Architecture

### Backend Structure

The backend follows a layered architecture located in `backend/app/`:

- **Models** (`models/`): SQLModel entities representing database tables and domain objects

- **CRUD** (`crud/`): Database access layer for all data operations

- **Routes** (`api/`): FastAPI REST endpoints organized by domain

- **Core** (`core/`): Core functionality and utilities
  - Configuration and settings
  - Database connection and session management
  - Security (JWT, password hashing, API keys)
  - Cloud storage (`cloud/storage.py`)
  - Document transformation (`doctransform/`)
  - Fine-tuning utilities (`finetune/`)
  - Langfuse observability integration (`langfuse/`)
  - Exception handlers and middleware

- **Services** (`services/`): Business logic services
  - Response service (`response/`): OpenAI Responses API integration, conversation management, and job execution

- **Celery** (`celery/`): Asynchronous task processing with RabbitMQ and Redis
  - Task definitions (`tasks/`)
  - Celery app configuration with priority queues
  - Beat scheduler and worker configuration


### Authentication & Security

- JWT-based authentication
- API key support for programmatic access
- Organization and project-level permissions

## Environment Configuration

The application uses different environment files:
- `.env` - Application environment configuration (use `.env.example` as template)
- `.env.test` - Test environment configuration


## Testing Strategy

- Tests located in `app/tests/`
- Factory pattern for test fixtures
- Automatic coverage reporting

## Code Standards

- Python 3.11+ with type hints
- Pre-commit hooks for linting and formatting
