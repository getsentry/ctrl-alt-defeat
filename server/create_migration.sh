#!/bin/bash
# Script to create a new database migration

# Check if message is provided
if [ -z "$1" ]; then
    echo "Usage: ./create_migration.sh \"Description of changes\""
    exit 1
fi

# Use environment variables if set
export DB_HOST=${DB_HOST:-localhost:5432}
export DB_NAME=${DB_NAME:-autobattler}

echo "Creating migration for database: $DB_NAME at $DB_HOST"
echo "Migration message: $1"

# Generate the migration
alembic revision --autogenerate -m "$1"

echo "Migration created successfully!"
echo "To apply migrations, run: ./migrate.sh"
