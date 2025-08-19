"""
Database connection and session management for PostgreSQL
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from urllib.parse import urlparse, urlunparse

from models import Base
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


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
    base_url = os.environ.get(
        "DATABASE_URL", "postgresql://user:password@localhost:5432/autobattler"
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

        try:
            # Create async engine with connection pooling
            self.engine = create_async_engine(
                self.async_database_url,
                echo=False,  # Set to True for SQL logging
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=3600,  # Recycle connections after 1 hour
            )

            # Create async session factory
            self.async_session_maker = sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )

            # Create tables if they don't exist
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            self._initialized = True
            print(
                f"Database initialized successfully at {self.async_database_url.split('@')[1]}"
            )

        except Exception as e:
            print(f"Failed to initialize database: {e}")
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
            finally:
                await session.close()

    async def health_check(self) -> bool:
        """Check if database is accessible"""
        try:
            async with self.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            print(f"Database health check failed: {e}")
            return False


# Global database manager instance
db_manager = DatabaseManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI endpoints to get database session"""
    async with db_manager.get_session() as session:
        yield session
