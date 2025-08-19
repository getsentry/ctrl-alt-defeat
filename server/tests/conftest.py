"""
Pytest configuration file - automatically loaded by pytest
"""
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

# Add the parent directory (server/) to the Python path
# so test files can import modules like battle_engine, item_effects, etc.
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set TEST_MODE environment variable for all tests
os.environ["TEST_MODE"] = "true"

# Configure test database if not already set
# Use a separate database specifically for server tests
if "DB_NAME" not in os.environ:
    os.environ["DB_NAME"] = "ctrl_alt_defeat_server_tests"
if "DB_HOST" not in os.environ:
    os.environ["DB_HOST"] = "localhost:5432"


@pytest.fixture(autouse=True)
def setup_test_mode():
    """Ensure TEST_MODE and test database are configured for all tests"""
    os.environ["TEST_MODE"] = "true"
    # Tests will use test database configured above
    yield
    # Keep TEST_MODE set after test


@pytest.fixture(scope="function")
async def transactional_db():
    """Fast transaction-based test isolation using SQLAlchemy

    This creates a transaction at the start of each test and rolls it back
    at the end, which is MUCH faster than truncating tables.
    """
    from database import Base, get_database_url
    from sqlalchemy.orm import sessionmaker

    # Get test database URL
    db_url = get_database_url(
        db_host=os.environ.get("DB_HOST"), db_name=os.environ.get("DB_NAME")
    )

    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    # Create engine with isolation level for nested transactions
    engine = create_async_engine(
        db_url,
        poolclass=NullPool,  # Don't pool connections in tests
        isolation_level="AUTOCOMMIT",  # Required for savepoints
    )

    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Start a connection and transaction
    async with engine.connect() as connection:
        # Start transaction
        trans = await connection.begin()

        # Configure session to use our connection
        async_session_maker = sessionmaker(
            connection, class_=AsyncSession, expire_on_commit=False
        )

        # Override the global session manager to use our transactional session
        import session_manager

        original_get_session = session_manager.db_manager.get_session

        async def get_test_session():
            async with async_session_maker() as session:
                yield session

        session_manager.db_manager.get_session = get_test_session

        yield async_session_maker

        # Restore original session getter
        session_manager.db_manager.get_session = original_get_session

        # Rollback the transaction - this undoes all changes from the test
        await trans.rollback()

    await engine.dispose()


@pytest.fixture(scope="function")
def clean_database():
    """Simplified fixture for FastAPI TestClient tests

    Since TestClient creates its own app instance, we can't easily
    inject a transactional session. This fixture provides basic cleanup.

    For better performance, consider refactoring tests to use
    async client with transactional_db fixture.
    """
    # The TestClient will use the normal database connection
    # We rely on test isolation through separate test database
    yield

    # Optional: Reset database after test if needed
    # This is slow but ensures complete cleanup
    if os.environ.get("FORCE_DB_RESET") == "true":
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        client.post("/test/reset-database")
