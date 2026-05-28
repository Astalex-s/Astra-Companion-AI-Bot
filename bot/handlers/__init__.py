from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from bot.handlers.start import start_command, help_command
from bot.handlers.chat import chat_message, new_session_command
from bot.handlers.facts import facts_command, forget_command, forget_all_command
from bot.handlers.notes import note_command, notes_command, note_edit_command, note_delete_command
from bot.handlers.search import search_command
from bot.handlers.tasks import (
    task_command, tasks_command, task_done_command,
    task_progress_command, task_delete_command,
)
from bot.handlers.reminders import remind_command, reminders_command, remind_delete_command, snooze_callback
from bot.handlers.settings import (
    settings_command, stats_command, profile_command,
    set_language_command, set_model_command, set_timezone_command,
)
from bot.handlers.export import export_command


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
    app.add_handler(CommandHandler("task", task_command))
    app.add_handler(CommandHandler("tasks", tasks_command))
    app.add_handler(CommandHandler("task_done", task_done_command))
    app.add_handler(CommandHandler("task_progress", task_progress_command))
    app.add_handler(CommandHandler("task_delete", task_delete_command))
    app.add_handler(CommandHandler("remind", remind_command))
    app.add_handler(CommandHandler("reminders", reminders_command))
    app.add_handler(CommandHandler("remind_delete", remind_delete_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("set_language", set_language_command))
    app.add_handler(CommandHandler("set_model", set_model_command))
    app.add_handler(CommandHandler("set_timezone", set_timezone_command))
    app.add_handler(CommandHandler("export", export_command))

    # Callback queries (inline buttons)
    app.add_handler(CallbackQueryHandler(snooze_callback, pattern=r"^snooze:"))

    # Text messages — must be last (catch-all)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_message))
