# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI Platform named Kaapi built with FastAPI (backend) and PostgreSQL (database), containerized with Docker. The platform provides AI capabilities including OpenAI assistants, fine-tuning, document processing, and collection management.

## Key Commands

### Development

```bash
# Start development environment with auto-reload
source .venv/bin/activate
fastapi run --reload app/main.py

# Run backend tests
uv run bash scripts/tests-start.sh

# Seed data
uv run python -m app.seed_data.seed_data

# Run pre-commit
uv run pre-commit run --all-files

# Activate virtual environment
source .venv/bin/activate

# Generate new Migration
alembic revision --autogenerate -m 'Add new meta'
```

### Testing

```bash
# Run backend tests
uv run bash scripts/tests-start.sh
```

## Architecture

### Backend Structure

The backend follows a layered architecture:

- **API Layer** (`backend/app/api/`): FastAPI routes organized by domain
  - Authentication (`login.py`)
  - Core resources: `users.py`, `organizations.py`, `projects.py`
  - AI features: `assistants.py`, `fine_tuning.py`, `openai_conversation.py`
  - Document management: `documents.py`, `collections.py`, `doc_transformation_job.py`

- **Models** (`backend/app/models/`): SQLModel entities representing database tables
  - User system: User, Organization, Project, ProjectUser
  - AI components: Assistant, Thread, Message, FineTuning
  - Document system: Document, Collection, DocumentCollection, DocTransformationJob

- **CRUD Operations** (`backend/app/crud/`): Database operations for each model

- **Core Services** (`backend/app/core/`):
  - `providers.py`: OpenAI client management
  - `finetune/`: Fine-tuning pipeline (preprocessing, evaluation)
  - `doctransform/`: Document transformation services
  - `cloud/storage.py`: S3 storage integration
  - `langfuse/`: Observability and tracing

### Database

PostgreSQL with Alembic migrations. Key relationships:
- Organizations contain Projects
- Projects have Users (many-to-many via ProjectUser)
- Projects contain Collections and Documents
- Documents can belong to Collections (many-to-many)
- Projects have Assistants, Threads, and FineTuning jobs

### Authentication & Security

- JWT-based authentication
- API key support for programmatic access
- Role-based access control (User, Admin, Super Admin)
- Organization and project-level permissions

## Environment Configuration

Critical environment variables:
- `SECRET_KEY`: JWT signing key
- `POSTGRES_*`: Database connection
- `LOCAL_CREDENTIALS_ORG_OPENAI_API_KEY`: OpenAI API key
- `AWS_S3_BUCKET_PREFIX`: S3 storage configuration
- `LANGFUSE_*`: Observability configuration

## Testing Strategy

- Unit tests in `backend/app/tests/`
- Test fixtures use factory pattern
- Mock external services (OpenAI, S3) using `moto` and `openai_responses`
- Coverage reports generated automatically

## Code Standards

- Python 3.11+ with type hints
- Pre-commit hooks configured for consistency
