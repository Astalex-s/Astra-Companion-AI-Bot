import logging

from telegram.ext import ApplicationBuilder

from bot.config import settings
from bot.handlers import register_handlers
from bot.middleware.error_handler import error_handler

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

    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
