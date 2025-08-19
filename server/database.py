"""
Database connection and session management for PostgreSQL
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from models import Base
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Get database URL from environment
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://user:password@localhost:5432/autobattler"
)

# Convert to async URL if needed (postgresql:// -> postgresql+asyncpg://)
if DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
else:
    ASYNC_DATABASE_URL = DATABASE_URL


class DatabaseManager:
    """Manages database connections and sessions"""

    def __init__(self):
        self.engine = None
        self.async_session_maker = None
        self._initialized = False

    async def initialize(self):
        """Initialize the database connection"""
        if self._initialized:
            return

        try:
            # Create async engine with connection pooling
            self.engine = create_async_engine(
                ASYNC_DATABASE_URL,
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
                f"Database initialized successfully at {ASYNC_DATABASE_URL.split('@')[1]}"
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
