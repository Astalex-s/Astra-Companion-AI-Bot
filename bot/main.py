import logging

from telegram import BotCommand
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


BOT_COMMANDS = [
    BotCommand("menu", "Главное меню"),
    BotCommand("new", "Новый диалог"),
    BotCommand("search", "Поиск по памяти"),
    BotCommand("help", "Справка"),
]


async def post_init(app) -> None:
    """Called after the Application has been initialized (event loop is running)."""
    await app.bot.set_my_commands(BOT_COMMANDS)
    await app.bot.set_my_short_description(
        "AI-ассистент с памятью. Запоминаю факты, храню заметки и задачи, ищу по смыслу, напоминаю о важном."
    )
    await app.bot.set_my_description(
        "Персональный AI-помощник с долговременной памятью.\n\n"
        "Я запоминаю контекст между разговорами, храню заметки и задачи, "
        "выполняю поиск по смыслу и напоминаю о важном. Понимаю текст и голос.\n\n"
        "Просто напиши или скажи — я пойму, что нужно сделать."
    )
    start_scheduler(app)


async def post_shutdown(app) -> None:
    """Called before the Application shuts down."""
    stop_scheduler()


def main() -> None:
    logger.info("Starting AstraCompanion bot...")

    app = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    register_handlers(app)
    app.add_error_handler(error_handler)

    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
