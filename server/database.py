"""
Database connection and session management for PostgreSQL
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse, urlunparse

from models import Base
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


def parse_asyncpg_url(database_url: str) -> Tuple[str, Dict[str, Any]]:
    """Parse database URL and extract SSL parameters for asyncpg.

    Returns:
        Tuple of (clean_url, connect_args) where:
        - clean_url: URL without sslmode parameter
        - connect_args: Dict with SSL configuration for asyncpg
    """
    parsed_url = urlparse(database_url)
    query_params = parse_qs(parsed_url.query)

    # Check for sslmode in query parameters
    sslmode = query_params.get("sslmode", [None])[0]

    # Remove sslmode from URL as asyncpg doesn't accept it directly
    if "sslmode" in query_params:
        del query_params["sslmode"]
        # Reconstruct query string without sslmode
        if query_params:
            # Only create query string if there are remaining params
            new_query = "&".join([f"{k}={v[0]}" for k, v in query_params.items()])
        else:
            new_query = ""
        # Reconstruct URL without sslmode
        clean_url = urlunparse(
            (
                parsed_url.scheme,
                parsed_url.netloc,
                parsed_url.path,
                parsed_url.params,
                new_query,
                parsed_url.fragment,
            )
        )
    else:
        clean_url = database_url

    # Prepare connect_args based on SSL requirements
    connect_args = {}
    if sslmode:
        if sslmode == "require":
            connect_args["ssl"] = True
        elif sslmode == "disable":
            connect_args["ssl"] = False
        # Other modes like 'prefer', 'allow' can be added as needed

    return clean_url, connect_args


def get_database_url(
    db_host: Optional[str] = None, db_name: Optional[str] = None
) -> str:
    """Build database URL from environment or parameters

    Args:
        db_host: Optional database host (e.g. 'localhost:5432' or 'db.example.com:5432')
        db_name: Optional database name (e.g. 'autobattler_test')

    Returns:
        PostgreSQL connection URL
    """
    # Start with environment variable or default
    # Use postgres user with no password for local Docker PostgreSQL
    base_url = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:@localhost:5432/autobattler"
    )

    # If no overrides, return base URL
    if not db_host and not db_name:
        return base_url

    # Parse the URL
    parsed = urlparse(base_url)

    # Override host if provided
    if db_host:
        # Handle both 'localhost:5432' and 'localhost' formats
        if ":" in db_host:
            host, port = db_host.split(":", 1)
            netloc = f"{parsed.username}:{parsed.password}@{host}:{port}"
        else:
            netloc = (
                f"{parsed.username}:{parsed.password}@{db_host}:{parsed.port or 5432}"
            )
    else:
        netloc = parsed.netloc

    # Override database name if provided
    if db_name:
        path = f"/{db_name}"
    else:
        path = parsed.path

    # Reconstruct URL
    return urlunparse(
        (parsed.scheme, netloc, path, parsed.params, parsed.query, parsed.fragment)
    )


# Get database URL from environment or command line args
DATABASE_URL = get_database_url(
    db_host=os.environ.get("DB_HOST"), db_name=os.environ.get("DB_NAME")
)

# Convert to async URL if needed (postgresql:// -> postgresql+asyncpg://)
if DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
else:
    ASYNC_DATABASE_URL = DATABASE_URL


class DatabaseManager:
    """Manages database connections and sessions"""

    def __init__(self, db_host: Optional[str] = None, db_name: Optional[str] = None):
        self.engine = None
        self.async_session_maker = None
        self._initialized = False

        # Allow overriding database URL
        if db_host or db_name:
            self.database_url = get_database_url(db_host, db_name)
            if self.database_url.startswith("postgresql://"):
                self.async_database_url = self.database_url.replace(
                    "postgresql://", "postgresql+asyncpg://"
                )
            else:
                self.async_database_url = self.database_url
        else:
            self.database_url = DATABASE_URL
            self.async_database_url = ASYNC_DATABASE_URL

    async def initialize(self):
        """Initialize the database connection"""
        if self._initialized:
            return

        # First, try to create the database if it doesn't exist
        await self._ensure_database_exists()

        try:
            # Create async engine with connection pooling and fast timeout
            # Use NullPool for testing to avoid connection pool issues with TestClient
            import os

            from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool

            poolclass = (
                NullPool
                if os.environ.get("TEST_MODE") == "true"
                else AsyncAdaptedQueuePool
            )

            # Use shared function to handle SSL parameters
            clean_url, ssl_args = parse_asyncpg_url(self.async_database_url)

            # Prepare connect_args with SSL and other settings
            connect_args = {
                "server_settings": {"jit": "off"},
                "timeout": 2,  # Connection timeout in seconds
                "command_timeout": 5,  # Command timeout in seconds
            }
            # Merge SSL args
            connect_args.update(ssl_args)

            self.engine = create_async_engine(
                clean_url,
                echo=False,  # Set to True for SQL logging
                poolclass=poolclass,
                pool_pre_ping=(
                    True if poolclass == AsyncAdaptedQueuePool else False
                ),  # Verify connections before using
                connect_args=connect_args,
            )

            # Create async session factory first (needed for migrations)
            self.async_session_maker = sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )

            # Check and run migrations if needed
            await self.check_and_run_migrations()

            # In production, tables should be created via migrations
            # Only use create_all for development/testing if migrations haven't been run
            try:
                # Check if tables exist
                async with self.engine.begin() as conn:
                    result = await conn.execute(
                        text(
                            "SELECT EXISTS (SELECT FROM information_schema.tables "
                            "WHERE table_name = 'game_sessions')"
                        )
                    )
                    tables_exist = result.scalar()

                    if not tables_exist:
                        print("Tables don't exist, creating via create_all (dev mode)")
                        await conn.run_sync(Base.metadata.create_all)
                    else:
                        print(
                            "Tables already exist (created via migrations or previous run)"
                        )
            except Exception as e:
                print(f"Warning: Could not check table existence: {e}")
                # Fall back to create_all to ensure tables exist
                async with self.engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)

            self._initialized = True
            logger.info(
                f"Database initialized successfully at {self.async_database_url.split('@')[1]}"
            )

        except Exception:
            logger.exception("Failed to initialize database")
            raise

    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
            self._initialized = False

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async database session"""
        if not self._initialized:
            await self.initialize()

        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def _ensure_database_exists(self):
        """Create the database if it doesn't exist"""
        from urllib.parse import urlparse

        import asyncpg

        parsed = urlparse(self.database_url)
        db_name = parsed.path.lstrip("/")

        # Connect to postgres database to create our target database
        admin_url = self.database_url.replace(f"/{db_name}", "/postgres")
        if admin_url.startswith("postgresql://"):
            admin_url = admin_url.replace("postgresql://", "")
            # Parse connection details
            if "@" in admin_url:
                auth, netloc = admin_url.split("@", 1)
                if ":" in auth:
                    user, password = auth.split(":", 1)
                else:
                    user = auth
                    password = ""
            else:
                user = "postgres"
                password = ""
                netloc = admin_url

            if "/" in netloc:
                host_port, _ = netloc.split("/", 1)
            else:
                host_port = netloc

            if ":" in host_port:
                host, port = host_port.split(":", 1)
                port = int(port)
            else:
                host = host_port
                port = 5432

            try:
                # Try to create the database
                conn = await asyncpg.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password if password else None,
                    database="postgres",
                    timeout=2,
                )

                # Check if database exists
                exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname = $1)",
                    db_name,
                )

                if not exists:
                    # Create the database
                    await conn.execute(f'CREATE DATABASE "{db_name}"')
                    logger.info(f"Created database: {db_name}")

                await conn.close()
            except asyncpg.DuplicateDatabaseError:
                # Database already exists, that's fine
                pass
            except Exception as e:
                logger.warning(f"Could not ensure database exists: {e}")
                # Continue anyway - the main connection will fail if there's a real problem

    async def health_check(self) -> bool:
        """Check if database is accessible"""
        try:
            async with self.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception:
            logger.exception("Database health check failed")
            return False

    async def check_and_run_migrations(self):
        """Check if migrations need to be run and apply them"""
        import os
        import subprocess

        # Skip migration check in tests for performance
        if os.environ.get("SKIP_MIGRATION_CHECK") == "true":
            return

        # Set environment variables for alembic
        env = os.environ.copy()
        if hasattr(self, "db_host") and self.db_host:
            env["DB_HOST"] = self.db_host
        if hasattr(self, "db_name") and self.db_name:
            env["DB_NAME"] = self.db_name

        try:
            # Check current migration status
            result = subprocess.run(
                ["alembic", "current"],
                capture_output=True,
                text=True,
                env=env,
                cwd=os.path.dirname(__file__),  # Run in server directory
            )

            # Check if we need to run migrations
            if "head" not in result.stdout:
                logger.info(
                    "Database migrations are not up to date. Running migrations..."
                )

                # Run migrations
                migrate_result = subprocess.run(
                    ["alembic", "upgrade", "head"],
                    capture_output=True,
                    text=True,
                    env=env,
                    cwd=os.path.dirname(__file__),
                )

                if migrate_result.returncode == 0:
                    logger.info("Migrations applied successfully")
                else:
                    logger.error(f"Migration failed: {migrate_result.stderr}")
            else:
                logger.debug("Database migrations are up to date")

        except FileNotFoundError:
            logger.error("Alembic not found. Skipping migration check.")
        except Exception as e:
            logger.error(f"Could not check migrations: {e}")


# Global database manager instance
db_manager = DatabaseManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI endpoints to get database session"""
    async with db_manager.get_session() as session:
        yield session
