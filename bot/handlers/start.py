import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.menu import main_menu_keyboard

logger = logging.getLogger(__name__)

WELCOME_MESSAGE = (
    "Привет! Я AstraCompanion — твой персональный AI-ассистент с памятью.\n\n"
    "Я умею:\n"
    "— Вести диалог и запоминать контекст\n"
    "— Хранить заметки и задачи\n"
    "— Искать по всем данным по смыслу\n"
    "— Напоминать о важном\n"
    "— Понимать голосовые сообщения\n\n"
    "Просто напиши или скажи мне что-нибудь — я пойму.\n"
    "Например: «запиши заметку», «покажи задачи», «напомни завтра».\n\n"
    "Нажми /menu для навигации."
)

HELP_MESSAGE = (
    "Основные команды:\n\n"
    "/menu — главное меню\n"
    "/new — начать новый диалог\n"
    "/search <запрос> — поиск по памяти\n"
    "/help — эта справка\n\n"
    "Вы также можете просто писать или говорить голосом — "
    "бот сам поймёт, что вы хотите сделать."
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — send welcome message, pin it, show menu."""
    msg = await update.message.reply_text(WELCOME_MESSAGE)

    # Pin the welcome message
    try:
        await msg.pin(disable_notification=True)
    except Exception as e:
        logger.debug("Could not pin welcome message: %s", e)

    await update.message.reply_text("Главное меню:", reply_markup=main_menu_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_MESSAGE)
