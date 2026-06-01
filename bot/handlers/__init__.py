from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ConversationHandler, MessageHandler, filters,
)

from bot.handlers.start import start_command, help_command
from bot.handlers.chat import chat_message, new_session_command
from bot.handlers.voice import voice_message
from bot.handlers.menu import menu_command, menu_callback
from bot.handlers.facts import facts_command, forget_command, forget_all_command
from bot.handlers.notes import (
    note_command, note_text_received, WAITING_NOTE_TEXT,
    notes_command, note_edit_command, note_delete_command,
)
from bot.handlers.search import search_command
from bot.handlers.tasks import (
    task_command, task_text_received, WAITING_TASK_TEXT,
    tasks_command, task_done_command,
    task_progress_command, task_delete_command,
)
from bot.handlers.reminders import (
    remind_command, remind_text_received, WAITING_REMIND_TEXT,
    reminders_command, remind_delete_command, snooze_callback,
)
from bot.handlers.settings import (
    settings_command, stats_command, profile_command,
    set_language_command, set_model_command, set_timezone_command,
)
from bot.handlers.export import export_command


async def _cancel(update, context):
    context.user_data.pop("awaiting_input", None)
    await update.message.reply_text("Операция отменена.")
    return ConversationHandler.END


def register_handlers(app: Application) -> None:
    """Register all bot handlers."""

    # Conversation handlers (must be before plain CommandHandlers)
    note_conv = ConversationHandler(
        entry_points=[CommandHandler("note", note_command)],
        states={WAITING_NOTE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, note_text_received)]},
        fallbacks=[CommandHandler("cancel", _cancel)],
    )

    task_conv = ConversationHandler(
        entry_points=[CommandHandler("task", task_command)],
        states={WAITING_TASK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_text_received)]},
        fallbacks=[CommandHandler("cancel", _cancel)],
    )

    remind_conv = ConversationHandler(
        entry_points=[CommandHandler("remind", remind_command)],
        states={WAITING_REMIND_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, remind_text_received)]},
        fallbacks=[CommandHandler("cancel", _cancel)],
    )

    app.add_handler(note_conv)
    app.add_handler(task_conv)
    app.add_handler(remind_conv)

    # Simple commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("new", new_session_command))
    app.add_handler(CommandHandler("facts", facts_command))
    app.add_handler(CommandHandler("forget", forget_command))
    app.add_handler(CommandHandler("forget_all", forget_all_command))
    app.add_handler(CommandHandler("notes", notes_command))
    app.add_handler(CommandHandler("note_edit", note_edit_command))
    app.add_handler(CommandHandler("note_delete", note_delete_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("tasks", tasks_command))
    app.add_handler(CommandHandler("task_done", task_done_command))
    app.add_handler(CommandHandler("task_progress", task_progress_command))
    app.add_handler(CommandHandler("task_delete", task_delete_command))
    app.add_handler(CommandHandler("reminders", reminders_command))
    app.add_handler(CommandHandler("remind_delete", remind_delete_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("set_language", set_language_command))
    app.add_handler(CommandHandler("set_model", set_model_command))
    app.add_handler(CommandHandler("set_timezone", set_timezone_command))
    app.add_handler(CommandHandler("export", export_command))

    # Callback queries — menu and actions
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^(menu:|action:)"))
    app.add_handler(CallbackQueryHandler(snooze_callback, pattern=r"^snooze:"))

    # Voice messages
    app.add_handler(MessageHandler(filters.VOICE, voice_message))

    # Text messages — must be last (catch-all)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_message))
