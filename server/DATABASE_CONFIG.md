# Database Configuration

The server now supports configurable database connections for session persistence.

## Configuration Options

### Command-line Arguments

```bash
python main.py --db-host <host:port> --db-name <database_name>
```

- `--db-host`: Database server hostname and port (e.g., `localhost:5432`, `db.example.com:5432`)
- `--db-name`: Database name (e.g., `autobattler`, `autobattler_test`)

### Environment Variables

You can also set these via environment variables:

```bash
export DB_HOST=localhost:5432
export DB_NAME=autobattler_test
python main.py
```

Or use the full DATABASE_URL:

```bash
export DATABASE_URL=postgresql://user:password@localhost:5432/autobattler
python main.py
```

## Running Tests with Separate Databases

The project uses separate databases for different test scenarios to avoid conflicts:

- **Server tests**: `ctrl_alt_defeat_server_tests` (configured in pytest.ini and conftest.py)
- **Client tests**: `autobattler_test` (default for run_test_server.sh)
- **Development**: `autobattler` (default database)

To run tests with a separate database instance:

### Option 1: Use the test server script

```bash
./run_test_server.sh [port] [db_host] [db_name]

# Examples:
./run_test_server.sh  # Uses defaults: port 8001, localhost:5432, autobattler_test
./run_test_server.sh 8002  # Custom port
./run_test_server.sh 8001 localhost:5432 test_db  # All custom
```

### Option 2: Manual configuration

```bash
# Start server with test database
python main.py --port 8001 --db-host localhost:5432 --db-name autobattler_test

# In another terminal, run tests against the test server
export SERVER_URL=http://localhost:8001
python -m pytest tests/
```

## Database Setup

### PostgreSQL with Docker

```bash
# Start PostgreSQL for development
docker-compose up -d postgres

# This creates:
# - Database: autobattler
# - User: postgres
# - Password: password
# - Port: 5432
```

### Create Test Databases

```bash
# Connect to PostgreSQL
docker exec -it autobattler-postgres-1 psql -U postgres

# Create test database for client tests
CREATE DATABASE autobattler_test;

# Create separate test database for server tests
CREATE DATABASE ctrl_alt_defeat_server_tests;

\q
```

## Database Migrations

### Migration Storage

Database migrations are stored in `/server/alembic/versions/`

### Migration Commands

#### Create a new migration
```bash
# Automatically generate migration from model changes
./create_migration.sh "Description of changes"

# Or manually with alembic
alembic revision --autogenerate -m "Description of changes"
```

#### Apply migrations
```bash
# Apply all pending migrations
./migrate.sh

# Or manually with alembic
alembic upgrade head
```

#### Check migration status
```bash
alembic current
```

#### Rollback migrations
```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>
```

### Migration Workflow

1. **Initial Setup** (first time only):
   ```bash
   cd server
   ./migrate.sh  # Applies the initial migration
   ```

2. **After Model Changes**:
   ```bash
   # Generate migration for your changes
   ./create_migration.sh "Add new field to game_sessions"

   # Apply the migration
   ./migrate.sh
   ```

3. **For Different Databases**:
   ```bash
   # For test database
   DB_NAME=autobattler_test ./migrate.sh

   # For custom database
   DB_HOST=db.example.com:5432 DB_NAME=production ./migrate.sh
   ```

## Fallback Mode

If the database is unavailable, the server automatically falls back to in-memory session storage. This ensures the server remains operational even if the database connection fails.

You'll see this message when running in fallback mode:
```
WARNING: Using in-memory session storage (database unavailable)
```
