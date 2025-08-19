#!/bin/bash
# Script to run server with test database configuration
# Default database is for client tests; server tests use ctrl_alt_defeat_server_tests

# Default values
PORT=${1:-8001}
DB_HOST=${2:-localhost:5432}
DB_NAME=${3:-autobattler_test}  # Default for client tests

echo "Starting test server..."
echo "Port: $PORT"
echo "Database Host: $DB_HOST"
echo "Database Name: $DB_NAME"
echo ""
echo "Note: Server tests use 'ctrl_alt_defeat_server_tests' database"
echo "      Client tests use 'autobattler_test' database"

# Set test mode
export TEST_MODE=true

# Run server with test database configuration
python main.py --port $PORT --db-host "$DB_HOST" --db-name "$DB_NAME"
