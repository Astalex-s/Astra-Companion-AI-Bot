from telegram import Update
from telegram.ext import ContextTypes


WELCOME_MESSAGE = (
    "Привет! Я AstraCompanion — твой персональный AI-ассистент с памятью.\n\n"
    "Я умею:\n"
    "— Вести диалог и запоминать контекст\n"
    "— Хранить заметки и задачи\n"
    "— Искать по всем данным по смыслу\n"
    "— Напоминать о важном\n\n"
    "Просто напиши мне что-нибудь или используй /help для списка команд."
)

HELP_MESSAGE = (
    "Доступные команды:\n\n"
    "/start — приветствие\n"
    "/help — список команд\n"
    "/new — начать новый диалог\n"
    "/note <текст> — создать заметку\n"
    "/notes — список заметок\n"
    "/task <текст> — создать задачу\n"
    "/tasks — список задач\n"
    "/search <запрос> — поиск по памяти\n"
    "/facts — мои факты\n"
    "/remind <время> <текст> — напоминание\n"
    "/reminders — список напоминаний\n"
    "/settings — настройки\n"
    "/stats — статистика\n"
    "/export — экспорт данных"
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_MESSAGE)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_MESSAGE)
