from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.handlers.start import start_command, help_command
from bot.handlers.chat import chat_message, new_session_command
from bot.handlers.facts import facts_command, forget_command, forget_all_command
from bot.handlers.notes import note_command, notes_command, note_edit_command, note_delete_command
from bot.handlers.search import search_command


def register_handlers(app: Application) -> None:
    """Register all bot handlers."""
    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("new", new_session_command))
    app.add_handler(CommandHandler("facts", facts_command))
    app.add_handler(CommandHandler("forget", forget_command))
    app.add_handler(CommandHandler("forget_all", forget_all_command))
    app.add_handler(CommandHandler("note", note_command))
    app.add_handler(CommandHandler("notes", notes_command))
    app.add_handler(CommandHandler("note_edit", note_edit_command))
    app.add_handler(CommandHandler("note_delete", note_delete_command))
    app.add_handler(CommandHandler("search", search_command))

    # Text messages — must be last (catch-all)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_message))
