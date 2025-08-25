# Use Python 3.12 base image
FROM python:3.12

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app/

# Install system dependencies (added poppler-utils)
RUN apt-get update && apt-get install -y \
    curl \
    poppler-utils \
 && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

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
COPY scripts /app/scripts
COPY app /app/app
COPY alembic.ini /app/alembic.ini

# Expose port 80
EXPOSE 80


CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80", "--workers", "4"]
