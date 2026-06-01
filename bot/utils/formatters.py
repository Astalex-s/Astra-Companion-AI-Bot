import logging

from telegram import Message
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

TELEGRAM_MESSAGE_LIMIT = 4096


async def delete_previous_bot_message(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete the previous bot message stored in user_data."""
    prev_id = context.user_data.get("last_bot_message_id")
    if prev_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=prev_id)
        except Exception:
            pass  # Message already deleted or too old


async def save_bot_message(msg: Message, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save bot message ID for future cleanup."""
    context.user_data["last_bot_message_id"] = msg.message_id


def split_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split a long message into chunks that fit Telegram's limit."""
    if len(text) <= limit:
        return [text]

    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break

        # Try to split at last newline within limit
        split_pos = text.rfind("\n", 0, limit)
        if split_pos == -1:
            # No newline — split at last space
            split_pos = text.rfind(" ", 0, limit)
        if split_pos == -1:
            # No space — hard split
            split_pos = limit

        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip("\n")

    return chunks
