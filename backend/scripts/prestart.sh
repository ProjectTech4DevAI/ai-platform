#! /usr/bin/env bash

set -e
set -x

# Let the DB start
python app/backend_pre_start.py

# Run migrations
alembic upgrade head

# Initialize services
services=(
    app/initial_data.py
    app/initial_storage.py
    app/core/rbac/update_casbin_policies.py
)

for i in ${services[@]}; do
    python $i
done
