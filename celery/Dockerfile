# Use Python 3.12 base image
FROM python:3.12

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set working directory
WORKDIR /app/

# Install system dependencies
RUN apt-get update && apt-get install -y curl redis-tools

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Enable bytecode compilation and efficient dependency linking
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy dependency files from backend
COPY backend/pyproject.toml backend/uv.lock ./

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Copy backend application files
COPY backend/app /app/app

# Create logs directory
RUN mkdir -p /app/logs

# Default command to start worker
CMD ["python", "-m", "celery", "-A", "app.celery.celery_app", "worker", "--loglevel=info", "--concurrency=4"]
