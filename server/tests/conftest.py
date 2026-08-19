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

# Skip migration checks in tests for performance
os.environ["SKIP_MIGRATION_CHECK"] = "true"

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
    from sqlalchemy.orm import sessionmaker

    from database import Base, get_database_url

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


# A game seed whose round-one shop is five non-container items. Tests that buy
# something use it so the shop is the same every run.
# (Reseeded when the catalogue correction changed what shops offer.)
SHOP_SEED = 2

# Same, but one of the five covers more than one square, and the first three
# together cost less than the starting gold. Tests that need a multi-square
# item, or that buy several items in a row, use this one.
# (Reseeded when the catalogue correction changed what shops offer.)
MULTI_SQUARE_SHOP_SEED = 59


@pytest.fixture
def auth_client():
    """Test client with authentication setup"""
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)

    # Get a guest token
    response = client.post("/auth/guest")
    assert response.status_code == 200
    data = response.json()

    # Set the authorization header for all requests
    client.headers["Authorization"] = f"Bearer {data['access_token']}"
    client.user_id = data["user_id"]

    return client
