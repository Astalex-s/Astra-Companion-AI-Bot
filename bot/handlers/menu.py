import io
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.config import settings
from bot.database.postgres import async_session
from bot.database.chromadb_client import ChromaDBClient
from bot.database.models import User, Message, Note, Task, Fact, Reminder
from bot.services.user_service import UserService
from bot.services.note_service import NoteService
from bot.services.task_service import TaskService
from bot.services.reminder_service import ReminderService
from bot.services.search_service import SearchService
from bot.services.fact_extraction import FactExtractionService
from bot.services.export_service import ExportService
from bot.services.notion_service import NotionService
from sqlalchemy import select, func

logger = logging.getLogger(__name__)

_chroma = None


def _get_chroma() -> ChromaDBClient:
    global _chroma
    if _chroma is None:
        _chroma = ChromaDBClient()
    return _chroma


# --- Keyboard layouts ---

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Заметки", callback_data="menu:notes"),
            InlineKeyboardButton("✅ Задачи", callback_data="menu:tasks"),
        ],
        [
            InlineKeyboardButton("⏰ Напоминания", callback_data="menu:reminders"),
            InlineKeyboardButton("🔍 Поиск", callback_data="menu:search"),
        ],
        [
            InlineKeyboardButton("👤 Профиль", callback_data="menu:profile"),
            InlineKeyboardButton("📊 Статистика", callback_data="action:stats"),
        ],
        [
            InlineKeyboardButton("📤 Экспорт", callback_data="menu:export"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="action:settings"),
        ],
    ])


def notes_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Создать", callback_data="action:note_create"),
            InlineKeyboardButton("📋 Список", callback_data="action:notes_list"),
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")],
    ])


def tasks_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Создать", callback_data="action:task_create"),
            InlineKeyboardButton("📋 Активные", callback_data="action:tasks_list"),
        ],
        [
            InlineKeyboardButton("✅ Выполненные", callback_data="action:tasks_done"),
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")],
    ])


def reminders_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Создать", callback_data="action:remind_create"),
            InlineKeyboardButton("📋 Список", callback_data="action:reminders_list"),
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")],
    ])


def profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Мои факты", callback_data="action:facts"),
            InlineKeyboardButton("🗑 Забыть всё", callback_data="action:forget_all"),
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")],
    ])


def export_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("📄 JSON", callback_data="action:export_json"),
            InlineKeyboardButton("📊 CSV", callback_data="action:export_csv"),
            InlineKeyboardButton("📝 Markdown", callback_data="action:export_md"),
        ],
    ]
    if settings.notion_api_token:
        buttons.append([InlineKeyboardButton("🔗 Notion", callback_data="action:export_notion")])
    buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")])
    return InlineKeyboardMarkup(buttons)


# --- Command handler ---

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /menu — show main inline menu."""
    await update.message.reply_text("Главное меню:", reply_markup=main_menu_keyboard())


# --- Callback handler ---

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all menu: and action: callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data

    # Sub-menus
    if data == "menu:main":
        await query.edit_message_text("Главное меню:", reply_markup=main_menu_keyboard())
    elif data == "menu:notes":
        await query.edit_message_text("📝 Заметки:", reply_markup=notes_keyboard())
    elif data == "menu:tasks":
        await query.edit_message_text("✅ Задачи:", reply_markup=tasks_keyboard())
    elif data == "menu:reminders":
        await query.edit_message_text("⏰ Напоминания:", reply_markup=reminders_keyboard())
    elif data == "menu:profile":
        await query.edit_message_text("👤 Профиль:", reply_markup=profile_keyboard())
    elif data == "menu:search":
        await query.edit_message_text(
            "🔍 Отправьте поисковый запрос текстом или голосом.\n"
            "Или используйте команду /search <запрос>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")]
            ]),
        )
    elif data == "menu:export":
        await query.edit_message_text("📤 Выберите формат экспорта:", reply_markup=export_keyboard())

    # Actions — create (prompt for input)
    elif data == "action:note_create":
        context.user_data["awaiting_input"] = "note"
        await query.edit_message_text(
            "📝 Напишите текст заметки:\n\n(или отправьте голосовое сообщение)",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="action:cancel")]
            ]),
        )
    elif data == "action:task_create":
        context.user_data["awaiting_input"] = "task"
        await query.edit_message_text(
            "✅ Опишите задачу:\n\n(или отправьте голосовое сообщение)",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="action:cancel")]
            ]),
        )
    elif data == "action:remind_create":
        context.user_data["awaiting_input"] = "reminder"
        await query.edit_message_text(
            "⏰ Напишите напоминание с указанием времени:\n"
            "Например: завтра в 10:00 встреча с командой",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="action:cancel")]
            ]),
        )
    elif data == "action:cancel":
        context.user_data.pop("awaiting_input", None)
        await query.edit_message_text("Главное меню:", reply_markup=main_menu_keyboard())

    # Actions — list/view
    elif data == "action:notes_list":
        await _action_notes_list(query)
    elif data == "action:tasks_list":
        await _action_tasks_list(query, status=None)
    elif data == "action:tasks_done":
        await _action_tasks_list(query, status="done")
    elif data == "action:reminders_list":
        await _action_reminders_list(query)
    elif data == "action:facts":
        await _action_facts(query)
    elif data == "action:forget_all":
        await _action_forget_all(query)
    elif data == "action:stats":
        await _action_stats(query)
    elif data == "action:settings":
        await _action_settings(query)

    # Actions — export
    elif data == "action:export_json":
        await _action_export_file(query, "json")
    elif data == "action:export_csv":
        await _action_export_file(query, "csv")
    elif data == "action:export_md":
        await _action_export_file(query, "md")
    elif data == "action:export_notion":
        await _action_export_notion(query)


# --- Action implementations ---

async def _action_notes_list(query) -> None:
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=query.from_user.id)
        note_service = NoteService(session, _get_chroma())
        notes = await note_service.list_notes(user.id)

    if not notes:
        text = "Заметок не найдено."
    else:
        lines = ["📝 Ваши заметки:\n"]
        for n in notes:
            tags_str = f" [{', '.join(n.tags)}]" if n.tags else ""
            lines.append(f"[{n.id}] {n.summary or n.content[:60]}{tags_str}")
        lines.append(f"\nВсего: {len(notes)}")
        text = "\n".join(lines)

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:notes")]
    ]))


PRIORITY_ICONS = {"low": "⬜", "medium": "🟡", "high": "🟠", "urgent": "🔴"}


async def _action_tasks_list(query, status: str | None) -> None:
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=query.from_user.id)
        task_service = TaskService(session, _get_chroma())
        tasks = await task_service.list_tasks(user.id, status=status)

    if not tasks:
        label = " выполненных" if status == "done" else ""
        text = f"Задач{label} не найдено."
    else:
        title = "✅ Выполненные задачи" if status == "done" else "✅ Активные задачи"
        lines = [f"{title}:\n"]
        for t in tasks:
            icon = PRIORITY_ICONS.get(t.priority, "")
            s_icon = {"todo": "[ ]", "in_progress": "[~]", "done": "[x]"}.get(t.status, "[ ]")
            line = f"{s_icon} [{t.id}] {icon} {t.description[:70]}"
            if t.deadline:
                line += f" (до {t.deadline.strftime('%d.%m')})"
            lines.append(line)
        lines.append(f"\nВсего: {len(tasks)}")
        text = "\n".join(lines)

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:tasks")]
    ]))


async def _action_reminders_list(query) -> None:
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=query.from_user.id)
        reminder_service = ReminderService(session)
        reminders = await reminder_service.list_reminders(user.id)

    if not reminders:
        text = "Нет активных напоминаний."
    else:
        lines = ["⏰ Активные напоминания:\n"]
        for r in reminders:
            time_str = r.trigger_at.strftime("%d.%m.%Y %H:%M")
            recurring = " (повтор)" if r.is_recurring else ""
            lines.append(f"[{r.id}] {time_str}{recurring} — {r.text}")
        lines.append(f"\nВсего: {len(reminders)}")
        text = "\n".join(lines)

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:reminders")]
    ]))


async def _action_facts(query) -> None:
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=query.from_user.id)
        fact_service = FactExtractionService(session, _get_chroma())
        facts = await fact_service.get_user_facts(user.id)

    if not facts:
        text = "Пока не знаю о вас ничего. Расскажите о себе!"
    else:
        lines = ["👤 Что я знаю о вас:\n"]
        for f in facts:
            lines.append(f"[{f.id}] {f.category}: {f.key} = {f.value}")
        lines.append(f"\nВсего: {len(facts)} фактов")
        lines.append("Удалить: /forget <id>")
        text = "\n".join(lines)

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:profile")]
    ]))


async def _action_forget_all(query) -> None:
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=query.from_user.id)
        fact_service = FactExtractionService(session, _get_chroma())
        count = await fact_service.delete_all_facts(user.id)

    await query.edit_message_text(
        f"Удалено фактов: {count}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu:profile")]
        ]),
    )


async def _action_stats(query) -> None:
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=query.from_user.id)

        counts = {}
        for model, name in [(Message, "Сообщений"), (Note, "Заметок"), (Task, "Задач"), (Fact, "Фактов")]:
            counts[name] = (await session.execute(
                select(func.count()).select_from(model).where(model.user_id == user.id)
            )).scalar() or 0

        reminders_count = (await session.execute(
            select(func.count()).select_from(Reminder).where(
                Reminder.user_id == user.id, Reminder.status == "active"
            )
        )).scalar() or 0

    lines = ["📊 Статистика:\n"]
    for name, count in counts.items():
        lines.append(f"{name}: {count}")
    lines.append(f"Активных напоминаний: {reminders_count}")
    lines.append(f"\nЗарегистрирован: {user.created_at.strftime('%d.%m.%Y') if user.created_at else 'N/A'}")

    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")]
    ]))


async def _action_settings(query) -> None:
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=query.from_user.id)

    text = (
        f"⚙️ Настройки:\n\n"
        f"Язык: {user.language}\n"
        f"Модель AI: {user.ai_model}\n"
        f"Часовой пояс: {user.timezone}\n"
        f"Утренний дайджест: {'вкл' if user.morning_digest else 'выкл'}\n\n"
        f"Изменить:\n"
        f"/set_language ru|en\n"
        f"/set_model <model>\n"
        f"/set_timezone Europe/Moscow"
    )

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")]
    ]))


async def _action_export_file(query, fmt: str) -> None:
    chat = query.message.chat

    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create_user(telegram_id=query.from_user.id)

        export_service = ExportService(session)
        if fmt == "json":
            content = await export_service.export_json(user.id)
            filename = "astra_export.json"
        elif fmt == "csv":
            content = await export_service.export_csv(user.id)
            filename = "astra_export.csv"
        else:
            content = await export_service.export_markdown(user.id)
            filename = "astra_export.md"

    file = io.BytesIO(content.encode("utf-8"))
    file.name = filename

    await query.edit_message_text(f"📤 Экспорт ({fmt.upper()})...")
    await chat.send_document(document=file, filename=filename, caption=f"Экспорт данных ({fmt.upper()})")


async def _action_export_notion(query) -> None:
    if not settings.notion_api_token or not settings.notion_parent_page_id:
        await query.edit_message_text("Notion не настроен.")
        return

    await query.edit_message_text("📤 Экспорт в Notion...")

    try:
        async with async_session() as session:
            user_service = UserService(session)
            user = await user_service.get_or_create_user(telegram_id=query.from_user.id)
            notion_service = NotionService(session)
            url = await notion_service.export_all(user.id)

        await query.edit_message_text(
            f"Данные экспортированы в Notion!\n{url}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад", callback_data="menu:export")]
            ]),
        )
    except Exception as e:
        logger.error("Notion export failed: %s", e)
        await query.edit_message_text(
            f"Ошибка: {e}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад", callback_data="menu:export")]
            ]),
        )
