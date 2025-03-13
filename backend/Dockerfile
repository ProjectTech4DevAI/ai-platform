# Use Python 3.12 base image
FROM python:3.12

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app/

# Install system dependencies and Poetry
RUN apt-get update && apt-get install -y \
    curl \
    && curl -sSL https://install.python-poetry.org | python -

# Add Poetry's virtual environment to PATH
ENV PATH="/root/.local/bin:$PATH"

# Copy dependency files for installation
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --no-root

# Set Python path
ENV PYTHONPATH=/app

# Copy application files
COPY scripts /app/scripts
COPY app /app/app
COPY alembic.ini /app/alembic.ini

# Expose port 80
EXPOSE 80

# Command to run the application
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80", "--workers", "4"]
