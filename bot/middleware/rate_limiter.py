import time
import logging
from collections import defaultdict

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import settings

logger = logging.getLogger(__name__)

# user_id -> list of timestamps
_user_requests: dict[int, list[float]] = defaultdict(list)


async def check_rate_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user hasn't exceeded the rate limit. Returns True if allowed."""
    if not update.effective_user:
        return True

    user_id = update.effective_user.id
    now = time.time()
    window = 60.0  # 1 minute window
    limit = settings.rate_limit_per_minute

    # Clean old entries
    _user_requests[user_id] = [t for t in _user_requests[user_id] if now - t < window]

    if len(_user_requests[user_id]) >= limit:
        logger.warning("Rate limit exceeded for user_id=%d", user_id)
        if update.effective_message:
            await update.effective_message.reply_text(
                f"Слишком много сообщений. Лимит: {limit}/мин. Подождите немного."
            )
        return False

    _user_requests[user_id].append(now)
    return True
