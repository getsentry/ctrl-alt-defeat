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

## Running Tests with Separate Database

To run tests with a separate database instance to avoid conflicts:

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

### Create Test Database

```bash
# Connect to PostgreSQL
docker exec -it autobattler-postgres-1 psql -U postgres

# Create test database
CREATE DATABASE autobattler_test;
\q
```

## Migration Storage

Database migrations are stored in `/server/alembic/versions/`

To create a new migration:
```bash
cd server
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

## Fallback Mode

If the database is unavailable, the server automatically falls back to in-memory session storage. This ensures the server remains operational even if the database connection fails.

You'll see this message when running in fallback mode:
```
WARNING: Using in-memory session storage (database unavailable)
```
