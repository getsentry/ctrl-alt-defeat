"""
Pytest configuration file - automatically loaded by pytest
"""

import os
from contextlib import asynccontextmanager
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

# Add the parent directory (server/) to the Python path
# so test files can import modules like battle_engine, item_effects, etc.
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set TEST_MODE environment variable for all tests
os.environ["TEST_MODE"] = "true"

# Skip migration checks in tests for performance
os.environ["SKIP_MIGRATION_CHECK"] = "true"

if "DB_HOST" not in os.environ:
    os.environ["DB_HOST"] = "localhost:5432"

#: Every database this harness has ever made is named for it, so the ones a
#: killed run left behind can be recognised and dropped.
TEST_DB_PREFIX = "cad_tests_"

#: What to fall back to where a database cannot be made -- no permission, or
#: no server to ask. A shared one that is never emptied, which is what this
#: replaces.
SHARED_DB = "ctrl_alt_defeat_server_tests"


def _server() -> dict:
    """Which Postgres to ask, read from the environment and nothing else.

    Not through `database.get_database_url`, which is the mistake this used to
    make: `database.py` works out the URL it will use *as it is imported*, so
    importing it here -- before DB_NAME is set two lines below -- bound every
    test in the run to the default database. Which is the developer's own, and
    is where a suite that believed it had a database of its own quietly wrote
    two hundred users.
    """
    from urllib.parse import urlparse

    url = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:@localhost:5432/autobattler")
    parsed = urlparse(url)
    host, port = parsed.hostname or "localhost", parsed.port or 5432
    if os.environ.get("DB_HOST"):
        host, _, given = os.environ["DB_HOST"].partition(":")
        port = int(given or 5432)
    return {"host": host, "port": port,
            "user": parsed.username or "postgres", "password": parsed.password}


async def _make_database(name: str) -> None:
    """Make this run its own database, and sweep up after the runs before it"""
    import asyncpg

    connection = await asyncpg.connect(database="postgres", **_server())
    try:
        # A run that was killed leaves its database behind. Nothing else is
        # named like this, so anything still here is ours and is finished with.
        left = await connection.fetch(
            "SELECT datname FROM pg_database WHERE datname LIKE $1",
            TEST_DB_PREFIX + "%")
        for row in left:
            await connection.execute(
                f'DROP DATABASE IF EXISTS "{row["datname"]}" WITH (FORCE)')
        await connection.execute(f'CREATE DATABASE "{name}"')
    finally:
        await connection.close()


async def _drop_database(name: str) -> None:
    import asyncpg

    connection = await asyncpg.connect(database="postgres", **_server())
    try:
        await connection.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    finally:
        await connection.close()


# A database of this run's own, made here rather than in a fixture because
# `database.py` reads DB_NAME as it is imported, and a fixture runs too late.
#
# The tests shared one database that nothing ever emptied, so a run started on
# top of every run before it -- fourteen hundred users, a thousand sessions --
# and anything that counted rows had to count around them. Making a fresh one
# costs about a third of a second against a suite that takes forty seconds.
_OWN_DB = ""
if "DB_NAME" not in os.environ:
    import asyncio
    import uuid

    _OWN_DB = TEST_DB_PREFIX + uuid.uuid4().hex[:12]
    try:
        asyncio.run(_make_database(_OWN_DB))
        os.environ["DB_NAME"] = _OWN_DB
    except Exception as why:  # no server, or no permission to make one
        print(f"Could not make a database for this run ({why}). "
              f"Falling back to {SHARED_DB}, which nothing empties.")
        _OWN_DB = ""
        os.environ["DB_NAME"] = SHARED_DB


def pytest_sessionfinish(session, exitstatus):
    """Throw this run's database away, whatever the run did"""
    if not _OWN_DB:
        return
    import asyncio

    try:
        asyncio.run(_drop_database(_OWN_DB))
    except Exception as why:
        print(f"Could not drop {_OWN_DB} ({why}). It will be swept up next run.")


@pytest.fixture(autouse=True)
def setup_test_mode():
    """Ensure TEST_MODE and test database are configured for all tests"""
    os.environ["TEST_MODE"] = "true"
    # Tests will use test database configured above
    yield
    # Keep TEST_MODE set after test


# An async fixture needs pytest_asyncio's decorator under strict mode, which
# this never had -- so every test that asked for it errored out at setup, and
# no test asked for it until now.
@pytest_asyncio.fixture(scope="function")
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

        # As a context manager, because that is how every caller uses it:
        # `async with db_manager.get_session() as db`. Swapped in as a bare
        # async generator, the first thing to reach for it raised
        # "'async_generator' object does not support the asynchronous context
        # manager protocol" -- which nothing found, because nothing used this
        # fixture until now.
        @asynccontextmanager
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


# Seeds whose round-one shop has the shape a test needs, searched for rather
# than written down.
#
# They were three numbers, re-picked by hand every time the shop's pool changed
# -- and it changes whenever an item's availability is corrected or a clause is
# built, which is now most weeks. Every re-pick was found by a test failing
# somewhere else for a reason it was not about, with a message telling the next
# person to go and pick another one.
#
# So the property is written instead, and the number is looked up. A search
# costs a fraction of a second at import and never goes stale.


def _seed_where(wanted, described: str, tries: int = 800) -> int:
    """The lowest seed whose round-one shop satisfies `wanted`."""
    from main import generate_shop_items

    for seed in range(tries):
        offers = [o for o in generate_shop_items(1, seed=seed, held=set()) if o]
        if len(offers) == 5 and wanted(offers):
            return seed
    raise AssertionError(f"no seed in {tries} offers {described}")


def _one_row(offer) -> bool:
    """At most two squares across and one deep.

    The starting racks are 2x2 at (2,3), (4,3) and (6,3), and these tests buy
    at fixed positions including (2,4) -- the bottom row of the first rack.
    Anything two squares tall hangs off the end of it.
    """
    squares = [tuple(square) for square in offer.shape]
    return max(x for x, _ in squares) < 2 and max(y for _, y in squares) < 1


def _two_across(offer) -> bool:
    """Exactly two squares side by side, which is what a turn is tested on"""
    return sorted(tuple(square) for square in offer.shape) == [(0, 0), (1, 0)]


def _starting_gold() -> int:
    """What a run starts with, read from where the session reads it.

    It was written down here as 12, from a stale default and comment in
    schemas.py, and the real figure is `ROUND_GOLD[0]`. A shop chosen for
    being unaffordable at 12 was affordable at 13, and every one of its five
    offers got bought.
    """
    from main import ROUND_GOLD

    return ROUND_GOLD[0]


STARTING_GOLD = _starting_gold()

# Five non-container items, every one of which fits where these tests buy.
SHOP_SEED = _seed_where(
    lambda offers: all(not o.is_container and _one_row(o) for o in offers),
    "five fitting items",
)

# Five items that cannot all be bought. One test buys the lot to storage and
# needs the gold to run out before the shop does, so shape does not matter and
# price does -- a sale is rolled with the shop, and a marked-down item is what
# the player is actually charged.
UNAFFORDABLE_SHOP_SEED = _seed_where(
    lambda offers: all(not o.is_container for o in offers)
    and sum(o.price for o in offers) > STARTING_GOLD,
    "five items that cannot all be afforded",
)

# The first two offers each cover one square, and both can be bought. Two
# tests buy at (2,3) and (3,3), which are neighbours: anything two across at
# the first position is standing on the second.
TWO_SINGLE_SQUARES_SHOP_SEED = _seed_where(
    lambda offers: all(not o.is_container for o in offers)
    and all(len(o.shape) == 1 for o in offers[:2])
    and sum(o.price for o in offers[:2]) <= STARTING_GOLD,
    "two single-square items that can be bought together",
)

# The same, and one of them is two squares across, and the first three can be
# bought together. Tests that turn an item, or buy several in a row, use this.
MULTI_SQUARE_SHOP_SEED = _seed_where(
    lambda offers: all(not o.is_container and _one_row(o) for o in offers)
    and any(_two_across(o) for o in offers)
    and sum(o.cost for o in offers[:3]) <= STARTING_GOLD,
    "five fitting items, one two across, three affordable together",
)

# One of the offers is marked down. A sale is a roll per item, so which seeds
# have one moves with the pool like everything else here.
SALE_SHOP_SEED = _seed_where(
    lambda offers: any(o.on_sale and o.price < o.cost for o in offers),
    "an item on sale",
)

SINGLE_SQUARE_SHOP_SEED = _seed_where(
    lambda offers: any(not o.is_container and len(o.shape) == 1 for o in offers),
    "an item covering exactly one square",
)


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
