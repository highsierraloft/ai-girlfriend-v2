"""Main entry point for the AI Girlfriend Telegram Bot."""

import asyncio
import logging
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.config.settings import settings
from app.bot.main import create_application


def setup_logging() -> None:
    """Set up logging configuration."""
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=getattr(logging, settings.log_level.upper()),
        stream=sys.stdout,
    )
    
    # Reduce noise from external libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def main() -> None:
    """Main entry point for the bot."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting AI Girlfriend Bot v0.1.0")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Webhook URL: {settings.webhook_url}")

    async def run_bot():
        """Run the bot within the same event loop."""
        try:
            # Create application using our existing function
            from app.bot.main import create_application
            application = await create_application()
            
            # Initialize and start the bot
            await application.initialize()
            
            if settings.webhook_url:
                logger.info("Starting bot in webhook mode")
                await application.start()
                await application.updater.start_webhook(
                    listen=settings.webhook_host,
                    port=settings.webhook_port,
                    url_path=settings.webhook_path,
                    webhook_url=settings.webhook_url,
                    secret_token=settings.webhook_secret,
                )
            else:
                logger.info("Starting bot in polling mode")
                await application.start()
                await application.updater.start_polling(drop_pending_updates=True)
            
            # Keep the application running
            import signal
            
            # Setup signal handlers for graceful shutdown
            stop_event = asyncio.Event()
            
            def signal_handler(signum, frame):
                logger.info(f"Received signal {signum}, shutting down...")
                stop_event.set()
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            # Wait for stop signal
            await stop_event.wait()
                
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            # Try cleanup
            try:
                if 'application' in locals() and application.bot_data.get('cleanup'):
                    await application.bot_data['cleanup']()
            except Exception:
                pass
            sys.exit(1)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        finally:
            # Final cleanup
            try:
                if 'application' in locals() and application.bot_data.get('cleanup'):
                    await application.bot_data['cleanup']()
            except Exception:
                pass
            logger.info("Bot shutdown complete")

    try:
        # Run everything in one event loop
        asyncio.run(run_bot())
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 