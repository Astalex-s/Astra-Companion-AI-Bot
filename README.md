# AstraCompanion AI Bot

<p align="center">
  <img src="bot_avatar.png" alt="AstraCompanion" width="200">
</p>

<p align="center">
  Персональный AI-ассистент в Telegram с долговременной памятью и семантическим поиском.
</p>

## О проекте

AstraCompanion — Telegram-бот, который выступает в роли интеллектуального персонального помощника. Ключевое отличие от обычных чат-ботов — **долговременная память** на основе векторной базы данных. Бот помнит контекст взаимодействия с пользователем, хранит заметки и задачи, выполняет семантический поиск и устанавливает напоминания.

### Возможности

- **Диалог с AI** — осмысленный диалог с сохранением контекста сессии и обогащением ответов из долговременной памяти
- **Долговременная память** — автоматическое извлечение фактов о пользователе из разговора (имя, профессия, интересы)
- **Заметки** — создание, просмотр, редактирование и удаление с AI-генерацией тегов и описания
- **Задачи** — управление задачами с AI-определением приоритетов и дедлайнов
- **Семантический поиск** — поиск по всем данным (заметки, задачи, факты, диалоги) по смыслу
- **Напоминания** — создание на естественном языке с поддержкой повторяющихся событий
- **Голосовые сообщения** — распознавание речи через Whisper API с автоматическим определением намерений
- **Intent Detection** — понимание естественного языка: "запиши заметку...", "покажи задачи", "напомни завтра..." — работает и текстом, и голосом
- **Утренний дайджест** — ежедневная сводка задач и напоминаний
- **Inline-меню** — удобная навигация кнопками без запоминания команд
- **Экспорт в Notion** — красиво оформленная страница с фактами, заметками, задачами и напоминаниями
- **Экспорт в файлы** — JSON, CSV, Markdown
- **Шифрование данных** — AES-256 (Fernet) для персональной информации
- **Rate limiting** — защита от злоупотреблений

## Технический стек

| Компонент | Технология |
|-----------|-----------|
| Язык | Python 3.12 |
| Telegram SDK | python-telegram-bot 21.x |
| AI Framework | LangChain 0.3.x |
| AI API | OpenAI API (GPT-5.4-mini, Whisper, Embeddings) |
| Реляционная БД | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 (async) |
| Миграции | Alembic |
| Векторная БД | ChromaDB 0.6.x |
| Планировщик | APScheduler |
| Экспорт | Notion API (notion-client) |
| Шифрование | cryptography (Fernet) |
| Контейнеризация | Docker + Docker Compose |

## Архитектура

Проект построен на принципах **Pragmatic Modular Architecture** — три слоя без лишних абстракций:

```
bot/
|-- handlers/      # Входной слой: Telegram -> вызов сервиса -> ответ
|-- services/      # Бизнес-логика: один сервис = один домен
|-- database/      # Данные: модели + подключения
|-- middleware/     # Сквозная логика: auth, rate-limit, encryption
|-- utils/         # Чистые функции-хелперы
```

Зависимости идут только вниз: `handlers -> services -> database`.

```
               +-------------------+
               |   Telegram User   |
               +--------+----------+
                        |
               +--------v----------+
               |   Bot Application |
               | (python-telegram-bot)
               +--------+----------+
                        |
          +-------------+-------------+
          |                           |
   +------v------+          +--------v--------+
   |  Handlers   |          |   Middleware     |
   |  (menu,     |          | (auth, rate-limit|
   |   voice)    |          |  encryption)     |
   +------+------+          +--------+--------+
          |                           |
          +-------------+-------------+
                        |
          +-------------v--------------+
          |      Service Layer         |
          |  ChatService, NoteService  |
          |  TaskService, SearchService|
          |  IntentService, VoiceService
          +------+----------+---------+
                 |          |
          +------v---+  +--v----------+
          | LangChain|  |  Database   |
          | + OpenAI |  |   Layer     |
          +----------+  +--+-----+---+
                           |     |
                    +------v-+ +-v--------+
                    |Postgres| | ChromaDB |
                    +--------+ +----------+
```

## Установка и запуск

### Предварительные требования

- Docker и Docker Compose
- OpenAI API ключ
- (Опционально) Notion Integration Token

### 1. Клонирование репозитория

```bash
git clone https://github.com/your-username/AstraCompanionAIBot.git
cd AstraCompanionAIBot
```

### 2. Настройка переменных окружения

```bash
cp .env.example .env
```

Отредактируйте `.env`:

```env
# Обязательные
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key

# Опционально (Notion экспорт)
NOTION_API_TOKEN=your_notion_integration_token
NOTION_PARENT_PAGE_ID=your_notion_page_id
```

### 3. Запуск через Docker Compose

```bash
cd docker
docker-compose up -d
```

Это запустит три контейнера:
- **bot** — Telegram-бот
- **postgres** — PostgreSQL 16
- **chromadb** — ChromaDB (векторная БД)

### 4. Локальный запуск (для разработки)

```bash
# Создать виртуальное окружение
python -m venv venvAC
source venvAC/bin/activate  # Linux/Mac
# или: venvAC\Scripts\activate  # Windows

# Установить зависимости
pip install -r requirements.txt

# Запустить PostgreSQL и ChromaDB через Docker
cd docker
docker-compose up -d postgres chromadb
cd ..

# Применить миграции
alembic upgrade head

# Запустить бота
python -m bot.main
```

## Интерфейс бота

### Inline-меню

Бот управляется через удобное меню с кнопками. Команда `/menu` открывает главное меню:

```
 📝 Заметки     ✅ Задачи
 ⏰ Напоминания  🔍 Поиск
 👤 Профиль     📊 Статистика
 📤 Экспорт     ⚙️ Настройки
```

Каждый раздел содержит подменю с действиями (создать, просмотреть, удалить).

### Основные команды

| Команда | Описание |
|---------|----------|
| `/menu` | Главное меню с кнопками |
| `/new` | Начать новый диалог |
| `/search <запрос>` | Семантический поиск по всем данным |
| `/help` | Справка |

Все остальные действия доступны через inline-меню или естественный язык.

### Естественный язык и голос

Бот понимает команды на естественном языке — текстом и голосом:

- "Запиши заметку: купить молоко по дороге домой"
- "Покажи мои задачи"
- "Напомни завтра в 10 утра про встречу"
- "Что ты знаешь обо мне?"
- "Найди информацию о React"

### Настройки

Все настройки меняются кнопками через меню (⚙️ Настройки):

- **Язык** — RU / EN
- **Модель AI** — gpt-5.4-mini, gpt-4.1, gpt-4.1-mini, gpt-4o
- **Часовой пояс** — Москва, UTC, Екатеринбург
- **Утренний дайджест** — вкл/выкл + выбор времени

## Экспорт данных

### Notion

Через меню (📤 Экспорт → Notion) или команду `/export notion`.

Создает красиво оформленную страницу в Notion:
- Профиль пользователя (факты)
- Заметки с тегами и датами
- Задачи с чекбоксами и приоритетами
- Напоминания

При повторном экспорте — **обновляет** существующую страницу (не создает дубликат).

### Файлы

Через меню или команды:
```
/export json   # Все данные в JSON
/export csv    # Заметки и задачи в CSV
/export md     # Все данные в Markdown
```

## Структура проекта

```
AstraCompanionAIBot/
|-- bot/
|   |-- main.py                    # Точка входа
|   |-- config.py                  # Конфигурация из .env
|   |-- handlers/
|   |   |-- start.py               # /start, /help
|   |   |-- menu.py                # Inline-меню с кнопками
|   |   |-- chat.py                # Текстовые сообщения + intent detection
|   |   |-- voice.py               # Голосовые сообщения (Whisper)
|   |   |-- notes.py               # Заметки (ConversationHandler)
|   |   |-- tasks.py               # Задачи (ConversationHandler)
|   |   |-- reminders.py           # Напоминания (ConversationHandler)
|   |   |-- search.py              # Семантический поиск
|   |   |-- facts.py               # Факты о пользователе
|   |   |-- settings.py            # Настройки (text fallback)
|   |   |-- export.py              # Экспорт данных
|   |-- services/
|   |   |-- chat_service.py        # Диалог с AI + долговременная память
|   |   |-- intent_service.py      # Определение намерений пользователя
|   |   |-- voice_service.py       # Транскрибация через Whisper
|   |   |-- note_service.py        # CRUD заметок + AI-теги
|   |   |-- task_service.py        # CRUD задач + AI-приоритеты
|   |   |-- reminder_service.py    # Напоминания + парсинг времени
|   |   |-- search_service.py      # Семантический поиск
|   |   |-- fact_extraction.py     # Извлечение фактов из диалога
|   |   |-- embedding_service.py   # Векторизация текста (OpenAI)
|   |   |-- notion_service.py      # Экспорт в Notion
|   |   |-- export_service.py      # Экспорт в файлы
|   |   |-- user_service.py        # Управление пользователями
|   |   |-- scheduler.py           # Планировщик: напоминания + утренний дайджест
|   |-- database/
|   |   |-- models.py              # SQLAlchemy модели (6 таблиц)
|   |   |-- postgres.py            # Подключение к PostgreSQL
|   |   |-- chromadb_client.py     # Клиент ChromaDB
|   |   |-- migrations/            # Alembic миграции
|   |-- middleware/
|   |   |-- auth.py                # Аутентификация (whitelist)
|   |   |-- rate_limiter.py        # Rate limiting
|   |   |-- encryption.py          # Шифрование данных (Fernet)
|   |   |-- error_handler.py       # Глобальная обработка ошибок
|   |-- utils/
|       |-- formatters.py          # Форматирование + cleanup сообщений
|-- tests/                         # Юнит-тесты (pytest + pytest-asyncio)
|-- docker/
|   |-- Dockerfile
|   |-- docker-compose.yml
|-- bot_avatar.png                 # Аватар бота
|-- .env.example
|-- requirements.txt
|-- alembic.ini
```

## Модели данных

### PostgreSQL

| Таблица | Назначение |
|---------|-----------|
| **users** | Пользователи: telegram_id, настройки, язык, модель AI, дайджест, Notion page ID |
| **messages** | История диалогов: role, content, session_id, tokens_used |
| **notes** | Заметки: content, summary (AI), tags (AI), chromadb_id |
| **tasks** | Задачи: description, priority (AI), status, deadline (AI) |
| **facts** | Факты о пользователе: category, key, value, confidence |
| **reminders** | Напоминания: text, trigger_at, is_recurring, recurrence_rule |

### ChromaDB (векторные коллекции)

| Коллекция | Содержимое |
|-----------|-----------|
| `user_{id}_notes` | Векторы заметок |
| `user_{id}_tasks` | Векторы задач |
| `user_{id}_facts` | Векторы фактов |
| `user_{id}_messages` | Векторы сообщений |

## Переменные окружения

| Переменная | Описание | По умолчанию |
|-----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Токен Telegram бота | — (обязательно) |
| `OPENAI_API_KEY` | API ключ OpenAI | — (обязательно) |
| `OPENAI_MODEL` | Модель для генерации | gpt-5.4-mini |
| `OPENAI_EMBEDDING_MODEL` | Модель для эмбеддингов | text-embedding-3-small |
| `DATABASE_URL` | URL подключения к PostgreSQL | postgresql+asyncpg://... |
| `CHROMADB_HOST` | Хост ChromaDB | localhost |
| `CHROMADB_PORT` | Порт ChromaDB | 8000 |
| `BOT_ADMIN_IDS` | ID администраторов | — |
| `ALLOWED_USER_IDS` | Whitelist пользователей | — (все допущены) |
| `SESSION_TIMEOUT_MINUTES` | Таймаут сессии диалога | 30 |
| `MAX_CONTEXT_MESSAGES` | Макс. сообщений в контексте | 20 |
| `ENCRYPTION_KEY` | Ключ шифрования (Fernet) | — |
| `RATE_LIMIT_PER_MINUTE` | Лимит сообщений/мин | 30 |
| `NOTION_API_TOKEN` | Токен Notion интеграции | — |
| `NOTION_PARENT_PAGE_ID` | ID родительской страницы Notion | — |
| `LOG_LEVEL` | Уровень логирования | INFO |

## Тестирование

```bash
pytest
pytest --cov=bot --cov-report=term-missing
```

## Лицензия

Личный pet-проект для портфолио. Некоммерческое использование.

## Автор

Алексей Астафьев — [astaf.al.mi@gmail.com](mailto:astaf.al.mi@gmail.com)
