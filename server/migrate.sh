#!/bin/bash
# Script to apply database migrations

# Use environment variables if set
export DB_HOST=${DB_HOST:-localhost:5432}
export DB_NAME=${DB_NAME:-autobattler}

echo "Applying migrations to database: $DB_NAME at $DB_HOST"

# Check current migration status
echo "Current migration status:"
alembic current

# Apply all pending migrations
echo ""
echo "Applying pending migrations..."
alembic upgrade head

echo ""
echo "Migration complete! Current status:"
alembic current
