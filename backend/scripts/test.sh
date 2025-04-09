#!/bin/bash
set -e
set -x

# Run tests with coverage tracking
coverage run --source=app -m pytest

# Generate a human-readable coverage report in the terminal
coverage report --show-missing

# Generate an HTML report for local viewing
coverage html --title "${@-coverage}"

# Generate the XML report for Codecov
coverage xml
