"""Database connection management with SQLAlchemy async."""

import logging
from typing import AsyncGenerator, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)

# Database base class
Base = declarative_base()

# Global engine and session maker
engine = None
async_session_maker = None
_current_settings = None


def _get_settings():
    """Get settings from various sources."""
    global _current_settings
    
    if _current_settings is not None:
        return _current_settings
    
    # Try main settings first
    try:
        from app.config.settings import settings
        _current_settings = settings
        logger.debug("Using main settings for database")
        return settings
    except Exception as e:
        logger.debug(f"Could not load main settings: {e}")
        # Fallback to webhook settings
        try:
            from app.webhook.settings import webhook_settings
            _current_settings = webhook_settings
            logger.debug("Using webhook settings for database")
            return webhook_settings
        except Exception as e2:
            logger.error(f"Could not load any settings: main={e}, webhook={e2}")
            raise ValueError("No database settings available")


async def init_database(settings_override: Optional[Any] = None) -> None:
    """Initialize database connection."""
    global engine, async_session_maker, _current_settings
    
    # Use provided settings or load them
    if settings_override:
        _current_settings = settings_override
        settings = settings_override
    else:
        settings = _get_settings()
    
    logger.info("Initializing database connection...")
    
    # Create async engine
    engine = create_async_engine(
        settings.database_url,
        echo=getattr(settings, 'debug', False),
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
        # Auto-initialize database if not done
        await init_database()
    
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