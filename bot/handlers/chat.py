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
from bot.services.fact_extraction import FactExtractionService
from bot.utils.formatters import split_message

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

        chat_service = ChatService(session, chroma=chroma)
        response = await chat_service.get_response(
            user, update.message.text, force_new_session=force_new,
        )

        # Extract facts from user message (non-blocking, errors logged)
        try:
            fact_service = FactExtractionService(session, chroma)
            await fact_service.extract_and_save(user.id, update.message.text)
        except Exception as e:
            logger.warning("Fact extraction failed: %s", e)

    for chunk in split_message(response):
        await update.message.reply_text(chunk)


async def new_session_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /new command — reset conversation context."""
    context.user_data["force_new_session"] = True
    await update.message.reply_text("Начинаю новый диалог. Контекст сброшен.")
