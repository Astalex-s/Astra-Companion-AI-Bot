from telegram.ext import Application, CommandHandler

from bot.handlers.start import start_command, help_command


def register_handlers(app: Application) -> None:
    """Register all bot handlers."""
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
