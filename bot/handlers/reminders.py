from datetime import datetime, timedelta, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.database.postgres import async_session
from bot.services.user_service import UserService
from bot.services.reminder_service import ReminderService

WAITING_REMIND_TEXT = 0


async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """Handle /remind [time and text] — create a reminder or start conversation."""
    if context.args:
        text = " ".join(context.args)
        await _create_and_reply(update, text)
        return ConversationHandler.END

    await update.message.reply_text(
        "Напишите напоминание с указанием времени.\n"
        "Например: завтра в 10:00 встреча с командой"
    )
    return WAITING_REMIND_TEXT


async def remind_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle reminder text in conversation mode."""
    text = update.message.text
    if not text:
        await update.message.reply_text("Пустой текст. Попробуйте ещё раз или /cancel.")
        return WAITING_REMIND_TEXT

    await _create_and_reply(update, text)
    return ConversationHandler.END


async def _create_and_reply(update: Update, text: str) -> None:
    """Create reminder and send reply."""
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

        reminder_service = ReminderService(session)
        reminder = await reminder_service.create_reminder(user.id, text)

    if not reminder:
        await update.message.reply_text("Не удалось определить время. Попробуйте уточнить.")
        return

    time_str = reminder.trigger_at.strftime("%d.%m.%Y %H:%M UTC")
    await update.message.reply_text(
        f"Напоминание #{reminder.id} создано.\n"
        f"Время: {time_str}\n"
        f"Текст: {reminder.text}"
    )


async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reminders — list active reminders."""
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

        reminder_service = ReminderService(session)
        reminders = await reminder_service.list_reminders(user.id)

    if not reminders:
        await update.message.reply_text("Нет активных напоминаний.")
        return

    lines = ["Активные напоминания:\n"]
    for r in reminders:
        time_str = r.trigger_at.strftime("%d.%m.%Y %H:%M")
        recurring = " (повтор)" if r.is_recurring else ""
        lines.append(f"[{r.id}] {time_str}{recurring} — {r.text}")

    lines.append(f"\nВсего: {len(reminders)}")
    lines.append("Удалить: /remind_delete <id>")
    await update.message.reply_text("\n".join(lines))


async def remind_delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /remind_delete <id>."""
    if not context.args:
        await update.message.reply_text("Укажите ID: /remind_delete <id>")
        return

    try:
        reminder_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=update.effective_user.id)

        reminder_service = ReminderService(session)
        deleted = await reminder_service.delete_reminder(user.id, reminder_id)

    if deleted:
        await update.message.reply_text(f"Напоминание #{reminder_id} удалено.")
    else:
        await update.message.reply_text(f"Напоминание #{reminder_id} не найдено.")


async def snooze_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle snooze inline button callback."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    if len(parts) != 3:
        return

    reminder_id = int(parts[1])
    minutes = int(parts[2])
    new_time = datetime.utcnow() + timedelta(minutes=minutes)

    async with async_session() as session:
        reminder_service = ReminderService(session)
        reminder = await reminder_service.snooze(reminder_id, new_time)

    if reminder:
        time_str = new_time.strftime("%H:%M")
        await query.edit_message_text(f"Отложено до {time_str} UTC.")
    else:
        await query.edit_message_text("Напоминание не найдено.")


def make_snooze_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Create inline keyboard with snooze options."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("5 мин", callback_data=f"snooze:{reminder_id}:5"),
            InlineKeyboardButton("15 мин", callback_data=f"snooze:{reminder_id}:15"),
            InlineKeyboardButton("1 час", callback_data=f"snooze:{reminder_id}:60"),
        ]
    ])
