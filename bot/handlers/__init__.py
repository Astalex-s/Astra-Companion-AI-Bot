from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.handlers.start import start_command, help_command
from bot.handlers.chat import chat_message, new_session_command


def register_handlers(app: Application) -> None:
    """Register all bot handlers."""
    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("new", new_session_command))

    # Text messages — must be last (catch-all)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_message))
