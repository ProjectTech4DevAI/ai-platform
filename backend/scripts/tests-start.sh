#! /usr/bin/env bash
set -e
set -x

# Set environment for testing
export ENVIRONMENT=testing

python app/tests_pre_start.py

# Run pending migrations for test database
uv run alembic upgrade head
if [ $? -ne 0 ]; then
    echo 'Error: Test database migrations failed'
    exit 1
fi

bash scripts/test.sh "$@"
