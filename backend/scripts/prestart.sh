#! /usr/bin/env bash

set -e
set -x

# Let the DB start
python app/backend_pre_start.py
if [ $? -ne 0 ]; then
    echo 'Error: Failed to start database'
    exit 1
fi

# Run migrations
alembic upgrade head
if [ $? -ne 0 ]; then
    echo 'Error: Database migrations failed'
    exit 1
fi

# Run seed data script
python -m app.seed_data.seed_data
if [ $? -ne 0 ]; then
    echo 'Error: Database seeding failed'
    exit 1
fi

for i in ${services[@]}; do
    python $i
    if [ $? -ne 0 ]; then
        echo "Error: Failed to run $i"
        exit 1
    fi
done
