#!/bin/bash
# Script to run server with test database configuration

# Default values
PORT=${1:-8001}
DB_HOST=${2:-localhost:5432}
DB_NAME=${3:-autobattler_test}

echo "Starting test server..."
echo "Port: $PORT"
echo "Database Host: $DB_HOST"
echo "Database Name: $DB_NAME"

# Set test mode
export TEST_MODE=true

# Run server with test database configuration
python main.py --port $PORT --db-host "$DB_HOST" --db-name "$DB_NAME"
