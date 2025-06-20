"""Database connection management with SQLAlchemy async."""

import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.config.settings import settings

logger = logging.getLogger(__name__)

# Database base class
Base = declarative_base()

# Global engine and session maker
engine = None
async_session_maker = None


async def init_database() -> None:
    """Initialize database connection."""
    global engine, async_session_maker
    
    logger.info("Initializing database connection...")
    
    # Create async engine
    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    
    # Create session maker
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    logger.info("Database connection initialized")


async def get_database() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    if async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_database() -> None:
    """Close database connection."""
    global engine
    if engine:
        await engine.dispose()
        logger.info("Database connection closed") 