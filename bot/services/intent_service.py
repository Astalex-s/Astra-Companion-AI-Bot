import json
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.chromadb_client import ChromaDBClient
from bot.services.note_service import NoteService
from bot.services.task_service import TaskService
from bot.services.reminder_service import ReminderService
from bot.services.search_service import SearchService
from bot.services.fact_extraction import FactExtractionService

logger = logging.getLogger(__name__)

INTENT_PROMPT = """Ты — классификатор намерений пользователя AI-ассистента. Определи, что хочет пользователь.

Доступные намерения:
- create_note — создать/сохранить/запомнить заметку. params: {"text": "текст заметки"}
- list_notes — показать список заметок. params: {"tag": "тег или null"}
- create_task — создать задачу. params: {"description": "описание задачи"}
- list_tasks — показать задачи. params: {"status": "done" или null для активных}
- task_done — отметить задачу выполненной. params: {"task_id": число}
- delete_note — удалить заметку. params: {"note_id": число}
- delete_task — удалить задачу. params: {"task_id": число}
- create_reminder — создать напоминание. params: {"text": "полный текст с временем"}
- list_reminders — показать напоминания. params: {}
- delete_reminder — удалить напоминание. params: {"reminder_id": число}
- search — поиск по памяти. params: {"query": "поисковый запрос"}
- show_facts — показать СЫРОЙ СПИСОК фактов (только для явных запросов: "покажи факты", "список фактов", "мои факты"). params: {}
- forget_fact — удалить/забыть факт. params: {"fact_id": число}
- chat — обычный разговор, вопрос, просьба, ничего из вышеперечисленного. params: {}

Правила:
- Если пользователь просит "запиши заметку", "сохрани заметку", "создай заметку", "добавь заметку" — это create_note
- ВАЖНО: "запомни что я люблю кофе", "запомни меня зовут Алексей", "я живу в Москве" — это chat, НЕ create_note. Личная информация о пользователе сохраняется автоматически через диалог
- Если "покажи заметки", "мои заметки", "список заметок" — list_notes
- Если "удали заметку", "убери заметку" — delete_note
- Если "мне нужно сделать", "создай задачу", "добавь задачу" — create_task
- Если "мои задачи", "покажи задачи", "список задач" — list_tasks
- Если "удали задачу", "убери задачу" — delete_task
- Если "напомни мне", "создай напоминание" — create_reminder
- Если "удали напоминание", "убери напоминание" — delete_reminder
- Если "найди", "поищи", "что я записывал о" — search
- Если "покажи факты", "список фактов", "мои факты" — show_facts
- Если "забудь факт", "удали факт", "забудь что" — forget_fact
- ВАЖНО: вопросы о пользователе ("как меня зовут", "сколько мне лет", "что ты знаешь обо мне", "кто я") — это chat, НЕ show_facts. Бот должен ответить как в живом диалоге, используя память
- Если ни одно не подходит — chat

Верни JSON: {"intent": "...", "params": {...}}
Отвечай ТОЛЬКО JSON."""

PRIORITY_ICONS = {"low": "⬜", "medium": "🟡", "high": "🟠", "urgent": "🔴"}


class IntentService:
    """Detects user intent from natural language and executes the action."""

    def __init__(self, session: AsyncSession, chroma: ChromaDBClient) -> None:
        self.session = session
        self.chroma = chroma
        self._llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.0,
        )

    async def detect_intent(self, text: str) -> dict:
        """Detect user intent from natural language text."""
        messages = [
            SystemMessage(content=INTENT_PROMPT),
            HumanMessage(content=text),
        ]
        try:
            response = await self._llm.ainvoke(messages)
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
            return json.loads(content)
        except Exception as e:
            logger.warning("Intent detection failed: %s", e)
            return {"intent": "chat", "params": {}}

    async def execute_intent(self, user_id: int, intent_data: dict) -> str | None:
        """Execute detected intent and return formatted response. Returns None for 'chat'."""
        intent = intent_data.get("intent", "chat")
        params = intent_data.get("params", {})

        if intent == "chat":
            return None

        handler = {
            "create_note": self._handle_create_note,
            "list_notes": self._handle_list_notes,
            "delete_note": self._handle_delete_note,
            "create_task": self._handle_create_task,
            "list_tasks": self._handle_list_tasks,
            "task_done": self._handle_task_done,
            "delete_task": self._handle_delete_task,
            "create_reminder": self._handle_create_reminder,
            "list_reminders": self._handle_list_reminders,
            "delete_reminder": self._handle_delete_reminder,
            "search": self._handle_search,
            "forget_fact": self._handle_forget_fact,
            "show_facts": self._handle_show_facts,
        }.get(intent)

        if not handler:
            return None

        try:
            return await handler(user_id, params)
        except Exception as e:
            logger.error("Intent execution failed (%s): %s", intent, e)
            return f"Ошибка при выполнении команды: {e}"

    async def _handle_create_note(self, user_id: int, params: dict) -> str:
        text = params.get("text", "")
        if not text:
            return "Не удалось определить текст заметки."
        note_service = NoteService(self.session, self.chroma)
        note = await note_service.create_note(user_id, text)
        tags_str = ", ".join(note.tags) if note.tags else "нет"
        return f"Заметка #{note.id} сохранена.\nТеги: {tags_str}\nКратко: {note.summary}"

    async def _handle_list_notes(self, user_id: int, params: dict) -> str:
        tag = params.get("tag")
        note_service = NoteService(self.session, self.chroma)
        notes = await note_service.list_notes(user_id, tag=tag)
        if not notes:
            return "Заметок не найдено."
        lines = ["Ваши заметки:\n"]
        for n in notes:
            tags_str = ", ".join(n.tags) if n.tags else ""
            line = f"[{n.id}] {n.summary or n.content[:60]}"
            if tags_str:
                line += f" ({tags_str})"
            lines.append(line)
        lines.append(f"\nВсего: {len(notes)}")
        return "\n".join(lines)

    async def _handle_create_task(self, user_id: int, params: dict) -> str:
        description = params.get("description", "")
        if not description:
            return "Не удалось определить описание задачи."
        task_service = TaskService(self.session, self.chroma)
        task = await task_service.create_task(user_id, description)
        icon = PRIORITY_ICONS.get(task.priority, "")
        deadline_str = task.deadline.strftime("%d.%m.%Y %H:%M") if task.deadline else "не указан"
        return f"Задача #{task.id} создана.\nПриоритет: {icon} {task.priority}\nДедлайн: {deadline_str}"

    async def _handle_list_tasks(self, user_id: int, params: dict) -> str:
        status = params.get("status")
        task_service = TaskService(self.session, self.chroma)
        tasks = await task_service.list_tasks(user_id, status=status)
        if not tasks:
            label = f" (статус: {status})" if status else ""
            return f"Задач не найдено{label}."
        lines = ["Ваши задачи:\n"]
        for t in tasks:
            icon = PRIORITY_ICONS.get(t.priority, "")
            status_icon = {"todo": "[ ]", "in_progress": "[~]", "done": "[x]"}.get(t.status, "[ ]")
            line = f"{status_icon} [{t.id}] {icon} {t.description[:80]}"
            if t.deadline:
                line += f" (до {t.deadline.strftime('%d.%m')})"
            lines.append(line)
        lines.append(f"\nВсего: {len(tasks)}")
        return "\n".join(lines)

    async def _handle_task_done(self, user_id: int, params: dict) -> str:
        task_id = params.get("task_id")
        if not task_id:
            return "Не удалось определить ID задачи."
        task_service = TaskService(self.session, self.chroma)
        task = await task_service.update_status(user_id, int(task_id), "done")
        if task:
            return f"Задача #{task_id} выполнена!"
        return f"Задача #{task_id} не найдена."

    async def _handle_create_reminder(self, user_id: int, params: dict) -> str:
        text = params.get("text", "")
        if not text:
            return "Не удалось определить текст напоминания."
        reminder_service = ReminderService(self.session)
        reminder = await reminder_service.create_reminder(user_id, text)
        if not reminder:
            return "Не удалось определить время напоминания. Укажите время явно."
        time_str = reminder.trigger_at.strftime("%d.%m.%Y %H:%M")
        return f"Напоминание #{reminder.id} создано.\nВремя: {time_str} UTC\nТекст: {reminder.text}"

    async def _handle_list_reminders(self, user_id: int, params: dict) -> str:
        reminder_service = ReminderService(self.session)
        reminders = await reminder_service.list_reminders(user_id)
        if not reminders:
            return "Активных напоминаний нет."
        lines = ["Ваши напоминания:\n"]
        for r in reminders:
            time_str = r.trigger_at.strftime("%d.%m.%Y %H:%M")
            lines.append(f"[{r.id}] {time_str} — {r.text}")
        return "\n".join(lines)

    async def _handle_search(self, user_id: int, params: dict) -> str:
        query = params.get("query", "")
        if not query:
            return "Не удалось определить поисковый запрос."
        search_service = SearchService(self.chroma)
        results = await search_service.search_all(user_id, query)
        if not results:
            return "По запросу ничего не найдено."
        lines = [f"Результаты поиска по «{query}»:\n"]
        for r in results:
            lines.append(f"[{r['type_label']}] (score: {r['score']}) {r['text'][:120]}")
        return "\n".join(lines)

    async def _handle_delete_note(self, user_id: int, params: dict) -> str:
        note_id = params.get("note_id")
        if not note_id:
            return "Не удалось определить ID заметки."
        note_service = NoteService(self.session, self.chroma)
        deleted = await note_service.delete_note(user_id, int(note_id))
        return f"Заметка #{note_id} удалена." if deleted else f"Заметка #{note_id} не найдена."

    async def _handle_delete_task(self, user_id: int, params: dict) -> str:
        task_id = params.get("task_id")
        if not task_id:
            return "Не удалось определить ID задачи."
        task_service = TaskService(self.session, self.chroma)
        deleted = await task_service.delete_task(user_id, int(task_id))
        return f"Задача #{task_id} удалена." if deleted else f"Задача #{task_id} не найдена."

    async def _handle_delete_reminder(self, user_id: int, params: dict) -> str:
        reminder_id = params.get("reminder_id")
        if not reminder_id:
            return "Не удалось определить ID напоминания."
        reminder_service = ReminderService(self.session)
        deleted = await reminder_service.delete_reminder(user_id, int(reminder_id))
        return f"Напоминание #{reminder_id} удалено." if deleted else f"Напоминание #{reminder_id} не найдено."

    async def _handle_forget_fact(self, user_id: int, params: dict) -> str:
        fact_id = params.get("fact_id")
        if not fact_id:
            return "Не удалось определить ID факта."
        fact_service = FactExtractionService(self.session, self.chroma)
        deleted = await fact_service.delete_fact(user_id, int(fact_id))
        return f"Факт #{fact_id} удалён." if deleted else f"Факт #{fact_id} не найден."

    async def _handle_show_facts(self, user_id: int, params: dict) -> str:
        fact_service = FactExtractionService(self.session, self.chroma)
        facts = await fact_service.get_user_facts(user_id)
        if not facts:
            return "Фактов о вас пока нет."
        lines = ["Что я знаю о вас:\n"]
        for f in facts:
            lines.append(f"[{f.id}] {f.category}: {f.key} = {f.value}")
        lines.append(f"\nВсего: {len(facts)} фактов")
        return "\n".join(lines)
