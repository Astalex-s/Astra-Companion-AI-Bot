import logging

from telegram.ext import ApplicationBuilder

from bot.config import settings
from bot.handlers import register_handlers
from bot.middleware.error_handler import error_handler
from bot.services.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, settings.log_level),
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting AstraCompanion bot...")

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    register_handlers(app)
    app.add_error_handler(error_handler)

    start_scheduler(app)

    logger.info("Bot is running. Press Ctrl+C to stop.")
    try:
        app.run_polling()
    finally:
        stop_scheduler()


if __name__ == "__main__":
    main()
