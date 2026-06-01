from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.database.postgres import async_session
from bot.database.models import User, Message, Note, Task, Fact, Reminder
from bot.services.user_service import UserService
from bot.services.fact_extraction import FactExtractionService
from bot.database.chromadb_client import ChromaDBClient
from sqlalchemy import select, func

_chroma = None


def _get_chroma() -> ChromaDBClient:
    global _chroma
    if _chroma is None:
        _chroma = ChromaDBClient()
    return _chroma


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings — show settings menu."""
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

    await update.message.reply_text(
        f"Настройки:\n\n"
        f"Язык: {user.language}\n"
        f"Модель AI: {user.ai_model}\n"
        f"Часовой пояс: {user.timezone}\n"
        f"Утренний дайджест: {'вкл' if user.morning_digest else 'выкл'}\n"
        f"Время дайджеста: {user.digest_time}\n\n"
        f"Для изменения настроек используйте команды:\n"
        f"/set_language ru|en\n"
        f"/set_model gpt-4o|gpt-4o-mini\n"
        f"/set_timezone Europe/Moscow"
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats — show user statistics."""
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

        messages_count = (await session.execute(
            select(func.count()).select_from(Message).where(Message.user_id == user.id)
        )).scalar() or 0

        notes_count = (await session.execute(
            select(func.count()).select_from(Note).where(Note.user_id == user.id)
        )).scalar() or 0

        tasks_count = (await session.execute(
            select(func.count()).select_from(Task).where(Task.user_id == user.id)
        )).scalar() or 0

        facts_count = (await session.execute(
            select(func.count()).select_from(Fact).where(Fact.user_id == user.id)
        )).scalar() or 0

        reminders_count = (await session.execute(
            select(func.count()).select_from(Reminder).where(
                Reminder.user_id == user.id, Reminder.status == "active"
            )
        )).scalar() or 0

    await update.message.reply_text(
        f"Статистика:\n\n"
        f"Сообщений: {messages_count}\n"
        f"Заметок: {notes_count}\n"
        f"Задач: {tasks_count}\n"
        f"Фактов: {facts_count}\n"
        f"Активных напоминаний: {reminders_count}\n\n"
        f"Зарегистрирован: {user.created_at.strftime('%d.%m.%Y') if user.created_at else 'N/A'}"
    )


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /profile — show user profile with all facts."""
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

        fact_service = FactExtractionService(session, _get_chroma())
        facts = await fact_service.get_user_facts(user.id)

    lines = [f"Профиль: {user.first_name or user.username or 'Пользователь'}\n"]

    if facts:
        lines.append("Что я знаю о вас:")
        for f in facts:
            lines.append(f"  {f.key}: {f.value}")
    else:
        lines.append("Пока не знаю о вас ничего. Расскажите о себе!")

    await update.message.reply_text("\n".join(lines))


async def set_language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /set_language <ru|en>."""
    if not context.args or context.args[0] not in ("ru", "en"):
        await update.message.reply_text("Формат: /set_language ru|en")
        return

    lang = context.args[0]
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)
        user.language = lang
        await session.commit()

    await update.message.reply_text(f"Язык изменён на: {lang}")


async def set_model_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /set_model <model>."""
    allowed = ("gpt-5.4-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4o")
    if not context.args or context.args[0] not in allowed:
        await update.message.reply_text(f"Формат: /set_model {' | '.join(allowed)}")
        return

    model = context.args[0]
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)
        user.ai_model = model
        await session.commit()

    await update.message.reply_text(f"Модель AI изменена на: {model}")


async def set_timezone_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /set_timezone <tz>."""
    if not context.args:
        await update.message.reply_text("Формат: /set_timezone Europe/Moscow")
        return

    tz = context.args[0]
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)
        user.timezone = tz
        await session.commit()

    await update.message.reply_text(f"Часовой пояс изменён на: {tz}")
