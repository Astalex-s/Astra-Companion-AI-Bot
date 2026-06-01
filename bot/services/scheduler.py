import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from telegram.ext import Application

from bot.database.postgres import async_session
from bot.database.models import User, Task, Reminder
from bot.services.reminder_service import ReminderService
from bot.handlers.reminders import make_snooze_keyboard

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def check_reminders(app: Application) -> None:
    """Check for due reminders and send notifications."""
    async with async_session() as session:
        reminder_service = ReminderService(session)
        due = await reminder_service.get_due_reminders()

        for reminder in due:
            try:
                result = await session.execute(
                    select(User).where(User.id == reminder.user_id)
                )
                user = result.scalar_one_or_none()
                if not user:
                    continue

                keyboard = make_snooze_keyboard(reminder.id)
                await app.bot.send_message(
                    chat_id=user.telegram_id,
                    text=f"Напоминание: {reminder.text}",
                    reply_markup=keyboard,
                )

                await reminder_service.mark_triggered(reminder.id)
                logger.info("Sent reminder #%d to user %d", reminder.id, user.telegram_id)
            except Exception as e:
                logger.error("Failed to send reminder #%d: %s", reminder.id, e)


async def send_morning_digests(app: Application) -> None:
    """Send morning digest to users who have it enabled."""
    now = datetime.now(timezone.utc)
    current_time = now.strftime("%H:%M")

    async with async_session() as session:
        # Find users with digest enabled and matching time
        result = await session.execute(
            select(User).where(
                User.morning_digest == True,
                User.digest_time == current_time,
            )
        )
        users = result.scalars().all()

        for user in users:
            try:
                digest = await _build_digest(session, user.id)
                if digest:
                    await app.bot.send_message(chat_id=user.telegram_id, text=digest)
                    logger.info("Sent morning digest to user %d", user.telegram_id)
            except Exception as e:
                logger.error("Failed to send digest to user %d: %s", user.telegram_id, e)


async def _build_digest(session, user_id: int) -> str | None:
    """Build morning digest text for a user."""
    # Active tasks
    result = await session.execute(
        select(Task).where(Task.user_id == user_id, Task.status != "done")
        .order_by(Task.deadline.asc().nullslast())
    )
    tasks = result.scalars().all()

    # Today's reminders
    now = datetime.utcnow()
    today_end = now.replace(hour=23, minute=59, second=59)
    result = await session.execute(
        select(Reminder).where(
            Reminder.user_id == user_id,
            Reminder.status == "active",
            Reminder.trigger_at <= today_end,
        ).order_by(Reminder.trigger_at.asc())
    )
    reminders = result.scalars().all()

    if not tasks and not reminders:
        return None

    priority_icons = {"low": "⬜", "medium": "🟡", "high": "🟠", "urgent": "🔴"}
    lines = ["Доброе утро! Вот ваш дайджест на сегодня:\n"]

    if tasks:
        lines.append(f"✅ Задачи ({len(tasks)}):")
        for t in tasks[:10]:
            icon = priority_icons.get(t.priority, "")
            deadline = f" (до {t.deadline.strftime('%d.%m')})" if t.deadline else ""
            lines.append(f"  {icon} {t.description[:60]}{deadline}")
        if len(tasks) > 10:
            lines.append(f"  ...и ещё {len(tasks) - 10}")
        lines.append("")

    if reminders:
        lines.append(f"⏰ Напоминания на сегодня ({len(reminders)}):")
        for r in reminders:
            time_str = r.trigger_at.strftime("%H:%M")
            lines.append(f"  {time_str} — {r.text}")
        lines.append("")

    lines.append("Хорошего дня!")
    return "\n".join(lines)


def start_scheduler(app: Application) -> None:
    """Start the reminder and digest scheduler."""
    scheduler.add_job(
        check_reminders,
        "interval",
        seconds=30,
        args=[app],
        id="check_reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        send_morning_digests,
        "interval",
        minutes=1,
        args=[app],
        id="morning_digests",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started (reminders every 30s, digest check every 1m)")


def stop_scheduler() -> None:
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
