# Tech4Dev AI Platform

## Getting Started

### Prerequisite Services

Ensure PostgreSQL is installed and running on your machine. This guide assumes it is accessible on `localhost` via its default port.
Additionally, install either uv or poetry to manage dependencies.

### Platform Setup

Clone the repository:

```bash
git clone https://github.com/ProjectTech4DevAI/ai-platform.git
```

### Environment Variables

Create a `.env` file in the root folder with the following content:

```ini
PROJECT_NAME=ai-platform

# Database Configuration
POSTGRES_USER=postgres_user
POSTGRES_PASSWORD=postgres_password
POSTGRES_DB=ai_database
POSTGRES_PORT=5432
POSTGRES_SERVER=localhost

# API Keys
OPENAI_API_KEY="change if needed"

# Security & Auth
ENVIRONMENT=local
SECRET_KEY=$(openssl rand -hex 32)
FIRST_SUPERUSER=admin@example.com
FIRST_SUPERUSER_PASSWORD=admin@12345
```

To generate a secure `SECRET_KEY`, run:

```bash
openssl rand -hex 32
```

### Virtual Environment Setup

Enter the backend directory
```bash
cd ai-platform/backend
```

Ensure you are using Python 3.13.2 or higher. Set up a virtual environment and install dependencies:

```bash
uv sync  # If using uv
# OR
poetry install  # If using Poetry

source .venv/bin/activate  # Activate the .venv
```

### Database Migrations

For database migrations, refer to the [backend migration guide](https://github.com/ProjectTech4DevAI/ai-platform/blob/main/backend/README.md#migrations).

If you don't want to use migrations at all, uncomment the lines in the file at `./backend/app/core/db.py` that end in:

```python
from sqlmodel import SQLModel
SQLModel.metadata.create_all(engine)
```

Then run:

```bash
python app/initial_data.py
```

### Running the Backend

Start the backend server using Uvicorn:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Once running, you can access the API documentation:

```bash
http://localhost:8000/docs
```

## Further Documentation

Refer to the backend documentation for detailed setup and usage instructions:  
[Backend README](https://github.com/ProjectTech4DevAI/ai-platform/blob/main/backend/README.md)

