import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

from bot.database.postgres import async_session
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
                # Get user's telegram_id from the reminder's user relationship
                from bot.database.models import User
                from sqlalchemy import select

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


def start_scheduler(app: Application) -> None:
    """Start the reminder checking scheduler."""
    scheduler.add_job(
        check_reminders,
        "interval",
        seconds=30,
        args=[app],
        id="check_reminders",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Reminder scheduler started (checking every 30s)")


def stop_scheduler() -> None:
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Reminder scheduler stopped")
