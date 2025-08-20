#! /usr/bin/env bash
set -e
set -x

# Set environment for testing
export ENVIRONMENT=testing

python app/tests_pre_start.py

bash scripts/test.sh "$@"
