"""Main bot application setup and initialization."""

import logging
from datetime import time
from telegram.ext import Application
from telegram import Update
from telegram.ext import ContextTypes

from app.config.settings import settings
from app.database.connection import init_database, close_database
from app.services.rate_limiter import rate_limiter
from app.services.scheduler_service import SchedulerService
from .handlers import setup_handlers

logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a fallback message to user if possible."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # Try to send a fallback message to the user if it's a message update
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Oops! 😔 Something went wrong. Please try again in a moment! 💕",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")


async def daily_loan_replenishment_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job function for daily loan replenishment."""
    logger.info("Running daily loan replenishment job")
    try:
        stats = await SchedulerService.replenish_daily_loans()
        logger.info(f"Daily loan replenishment completed: {stats}")
    except Exception as e:
        logger.error(f"Daily loan replenishment job failed: {e}")


def setup_scheduler(application: Application) -> None:
    """Setup daily scheduled tasks."""
    logger.info("Setting up scheduler jobs...")
    
    # Schedule daily loan replenishment at 22:00 Europe/Kyiv
    # Convert timezone to time object
    replenishment_time = time(hour=22, minute=0, second=0)  # 22:00
    
    # Add daily job for loan replenishment
    application.job_queue.run_daily(
        daily_loan_replenishment_job,
        time=replenishment_time,
        name="daily_loan_replenishment"
    )
    
    logger.info(f"Scheduled daily loan replenishment at {replenishment_time} {settings.schedule_timezone}")
    
    # Log current loan statistics on startup
    async def log_initial_stats():
        try:
            stats = await SchedulerService.get_users_loan_stats()
            logger.info(f"Initial loan statistics: {stats}")
        except Exception as e:
            logger.error(f"Failed to get initial loan statistics: {e}")
    
    # Run initial stats in a few seconds after startup
    async def scheduler_init_job(context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.info("Scheduler initialized successfully")
    
    application.job_queue.run_once(
        scheduler_init_job,
        when=1,
        name="scheduler_init"
    )


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
    
    # Set up scheduler
    setup_scheduler(application)
    logger.info("Scheduler setup complete")
    
    # Add error handler
    application.add_error_handler(error_handler)
    logger.info("Error handler registered")
    
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