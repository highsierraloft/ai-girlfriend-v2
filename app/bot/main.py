"""Main bot application setup and initialization."""

import logging
from telegram.ext import Application

from app.config.settings import settings
from app.database.connection import init_database, close_database
from app.services.rate_limiter import rate_limiter
from .handlers import setup_handlers

logger = logging.getLogger(__name__)


async def setup_application_components(application: Application) -> None:
    """Setup application components for an existing application.
    
    Args:
        application: The bot application to setup
    """
    logger.info("Setting up application components...")
    
    # Initialize database
    await init_database()
    logger.info("Database initialized")
    
    # Initialize Redis rate limiter
    await rate_limiter.init_redis()
    logger.info("Redis rate limiter initialized")
    
    # Initialize AI service
    from app.services.ai_service import ai_service
    await ai_service.initialize()
    logger.info("AI service initialized")
    
    # Set up handlers
    setup_handlers(application)
    
    # Store cleanup function in application context for manual cleanup
    async def cleanup():
        """Clean up resources on shutdown."""
        logger.info("Cleaning up resources...")
        await rate_limiter.close_redis()
        from app.services.ai_service import ai_service
        await ai_service.close()
        await close_database()
        logger.info("Cleanup complete")
    
    # Store cleanup function in bot_data for later use
    application.bot_data['cleanup'] = cleanup
    
    logger.info("Application components setup successfully")


async def create_application() -> Application:
    """Create and configure the bot application."""
    logger.info("Creating bot application...")
    
    # Create application
    application = Application.builder().token(settings.telegram_token).build()
    
    # Setup components
    await setup_application_components(application)
    
    logger.info("Bot application created successfully")
    return application 