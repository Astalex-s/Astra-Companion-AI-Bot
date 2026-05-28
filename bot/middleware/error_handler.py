import logging
import traceback

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler for the bot."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        tb = traceback.format_exception(None, context.error, context.error.__traceback__)
        logger.debug("".join(tb))
        await update.effective_message.reply_text(
            "Произошла ошибка при обработке запроса. Попробуйте ещё раз."
        )
