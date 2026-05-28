import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import settings

logger = logging.getLogger(__name__)


async def check_user_allowed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user is allowed to use the bot. Returns True if allowed."""
    if not settings.allowed_ids:
        return True  # No whitelist configured — allow everyone

    user_id = update.effective_user.id if update.effective_user else None
    if user_id and user_id in settings.allowed_ids:
        return True

    logger.warning("Unauthorized access attempt from user_id=%s", user_id)
    if update.effective_message:
        await update.effective_message.reply_text(
            "Извините, у вас нет доступа к этому боту."
        )
    return False
