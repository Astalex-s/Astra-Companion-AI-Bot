import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.database.postgres import async_session
from bot.database.chromadb_client import ChromaDBClient
from bot.middleware.auth import check_user_allowed
from bot.middleware.rate_limiter import check_rate_limit
from bot.services.user_service import UserService
from bot.services.chat_service import ChatService
from bot.services.intent_service import IntentService
from bot.services.fact_extraction import FactExtractionService
from bot.services.note_service import NoteService
from bot.services.task_service import TaskService
from bot.services.reminder_service import ReminderService
from bot.utils.formatters import split_message, delete_previous_bot_message, save_bot_message

logger = logging.getLogger(__name__)

_chroma = None


def _get_chroma() -> ChromaDBClient:
    global _chroma
    if _chroma is None:
        _chroma = ChromaDBClient()
    return _chroma


async def chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages — AI dialog."""
    if not update.message or not update.message.text:
        return

    if not await check_user_allowed(update, context):
        return
    if not await check_rate_limit(update, context):
        return

    # Handle awaiting_input from menu buttons (delete, edit, done)
    awaiting = context.user_data.pop("awaiting_input", None)
    if awaiting:
        result = await _handle_awaiting_input(update, context, awaiting)
        if result is not None:
            await delete_previous_bot_message(update.effective_chat.id, context)
            msg = await update.message.reply_text(result)
            await save_bot_message(msg, context)
            return

    await update.message.chat.send_action(ChatAction.TYPING)

    force_new = context.user_data.pop("force_new_session", False)
    chroma = _get_chroma()

    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(
            telegram_id=update.effective_user.id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
        )

        text = update.message.text

        # Detect intent from natural language (e.g. "запиши заметку...")
        intent_service = IntentService(session, chroma)
        intent_data = await intent_service.detect_intent(text)
        intent = intent_data.get("intent", "chat")

        is_command = False
        if intent != "chat" and not force_new:
            response = await intent_service.execute_intent(user.id, intent_data)
            if response:
                is_command = True
            else:
                chat_service = ChatService(session, chroma=chroma)
                response = await chat_service.get_response(user, text)
        else:
            chat_service = ChatService(session, chroma=chroma)
            response = await chat_service.get_response(
                user, text, force_new_session=force_new,
            )

        # Extract facts from user message (non-blocking, errors logged)
        try:
            fact_service = FactExtractionService(session, chroma)
            await fact_service.extract_and_save(user.id, text)
        except Exception as e:
            logger.warning("Fact extraction failed: %s", e)

    # Delete previous bot message only for command responses, not AI dialog
    if is_command:
        await delete_previous_bot_message(update.effective_chat.id, context)

    msg = None
    for chunk in split_message(response):
        msg = await update.message.reply_text(chunk)

    if is_command and msg:
        await save_bot_message(msg, context)


async def _handle_awaiting_input(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str) -> str | None:
    """Handle text input from menu button prompts. Returns response text or None."""
    text = update.message.text.strip()
    chroma = _get_chroma()

    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

        if action == "note":
            note_service = NoteService(session, chroma)
            note = await note_service.create_note(user.id, text)
            tags_str = ", ".join(note.tags) if note.tags else "нет"
            return f"Заметка #{note.id} сохранена.\nОписание: {note.summary}\nТеги: {tags_str}"

        elif action == "task":
            task_service = TaskService(session, chroma)
            task = await task_service.create_task(user.id, text)
            icons = {"low": "⬜", "medium": "🟡", "high": "🟠", "urgent": "🔴"}
            icon = icons.get(task.priority, "")
            deadline = task.deadline.strftime("%d.%m.%Y %H:%M") if task.deadline else "не указан"
            return f"Задача #{task.id} создана.\nПриоритет: {icon} {task.priority}\nДедлайн: {deadline}"

        elif action == "reminder":
            reminder_service = ReminderService(session)
            reminder = await reminder_service.create_reminder(user.id, text)
            if not reminder:
                return "Не удалось определить время. Попробуйте уточнить."
            time_str = reminder.trigger_at.strftime("%d.%m.%Y %H:%M UTC")
            return f"Напоминание #{reminder.id} создано.\nВремя: {time_str}\nТекст: {reminder.text}"

        elif action == "note_edit":
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                return "Формат: <id> <новый текст>"
            try:
                note_id = int(parts[0])
            except ValueError:
                return "ID должен быть числом."
            note_service = NoteService(session, chroma)
            note = await note_service.edit_note(user.id, note_id, parts[1])
            return f"Заметка #{note_id} обновлена." if note else f"Заметка #{note_id} не найдена."

        elif action == "note_delete":
            try:
                note_id = int(text)
            except ValueError:
                return "ID должен быть числом."
            note_service = NoteService(session, chroma)
            deleted = await note_service.delete_note(user.id, note_id)
            return f"Заметка #{note_id} удалена." if deleted else f"Заметка #{note_id} не найдена."

        elif action == "task_done":
            try:
                task_id = int(text)
            except ValueError:
                return "ID должен быть числом."
            task_service = TaskService(session, chroma)
            task = await task_service.update_status(user.id, task_id, "done")
            return f"Задача #{task_id} выполнена!" if task else f"Задача #{task_id} не найдена."

        elif action == "task_delete":
            try:
                task_id = int(text)
            except ValueError:
                return "ID должен быть числом."
            task_service = TaskService(session, chroma)
            deleted = await task_service.delete_task(user.id, task_id)
            return f"Задача #{task_id} удалена." if deleted else f"Задача #{task_id} не найдена."

        elif action == "remind_delete":
            try:
                remind_id = int(text)
            except ValueError:
                return "ID должен быть числом."
            reminder_service = ReminderService(session)
            deleted = await reminder_service.delete_reminder(user.id, remind_id)
            return f"Напоминание #{remind_id} удалено." if deleted else f"Напоминание #{remind_id} не найдено."

    return None


async def new_session_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /new command — reset conversation context."""
    context.user_data["force_new_session"] = True
    await delete_previous_bot_message(update.effective_chat.id, context)
    msg = await update.message.reply_text("Начинаю новый диалог. Контекст сброшен.")
    await save_bot_message(msg, context)
