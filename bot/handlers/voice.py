import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.database.postgres import async_session
from bot.database.chromadb_client import ChromaDBClient
from bot.middleware.auth import check_user_allowed
from bot.middleware.rate_limiter import check_rate_limit
from bot.services.user_service import UserService
from bot.services.voice_service import transcribe_voice
from bot.services.intent_service import IntentService
from bot.services.chat_service import ChatService
from bot.services.fact_extraction import FactExtractionService
from bot.utils.formatters import split_message, delete_previous_bot_message, save_bot_message

logger = logging.getLogger(__name__)

_chroma = None


def _get_chroma() -> ChromaDBClient:
    global _chroma
    if _chroma is None:
        _chroma = ChromaDBClient()
    return _chroma


async def voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming voice messages: transcribe -> detect intent -> execute or chat."""
    if not update.message or not update.message.voice:
        return

    if not await check_user_allowed(update, context):
        return
    if not await check_rate_limit(update, context):
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    # Download and transcribe voice
    voice = update.message.voice
    voice_file = await context.bot.get_file(voice.file_id)
    voice_bytes = await voice_file.download_as_bytearray()

    try:
        text = await transcribe_voice(bytes(voice_bytes))
    except Exception as e:
        logger.error("Voice transcription failed: %s", e)
        await update.message.reply_text("Не удалось распознать голосовое сообщение.")
        return

    if not text:
        await update.message.reply_text("Не удалось распознать речь в сообщении.")
        return

    # Delete previous bot message and show transcribed text
    await delete_previous_bot_message(update.effective_chat.id, context)
    await update.message.reply_text(f"🎤 Распознано: {text}")
    await update.message.chat.send_action(ChatAction.TYPING)

    chroma = _get_chroma()

    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(
            telegram_id=update.effective_user.id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
        )

        # Detect intent
        intent_service = IntentService(session, chroma)
        intent_data = await intent_service.detect_intent(text)
        intent = intent_data.get("intent", "chat")

        is_command = False
        if intent != "chat":
            result = await intent_service.execute_intent(user.id, intent_data)
            if result:
                response = result
                is_command = True
            else:
                chat_service = ChatService(session, chroma=chroma)
                response = await chat_service.get_response(user, text)
        else:
            chat_service = ChatService(session, chroma=chroma)
            response = await chat_service.get_response(user, text)

        # Extract facts from voice text
        try:
            fact_service = FactExtractionService(session, chroma)
            await fact_service.extract_and_save(user.id, text)
        except Exception as e:
            logger.warning("Fact extraction from voice failed: %s", e)

    if is_command:
        await delete_previous_bot_message(update.effective_chat.id, context)

    msg = None
    for chunk in split_message(response):
        msg = await update.message.reply_text(chunk)

    if is_command and msg:
        await save_bot_message(msg, context)
