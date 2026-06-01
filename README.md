# AstraCompanion AI Bot

Персональный AI-ассистент в Telegram с долговременной памятью и семантическим поиском.

## О проекте

AstraCompanion — это Telegram-бот, который выступает в роли интеллектуального персонального помощника. Ключевое отличие от обычных чат-ботов — наличие **долговременной памяти** на основе векторной базы данных. Бот помнит контекст взаимодействия с пользователем, хранит заметки и задачи, выполняет семантический поиск и устанавливает напоминания.

### Возможности

- **Диалог с AI** — осмысленный диалог с сохранением контекста сессии и обогащением ответов из долговременной памяти
- **Долговременная память** — автоматическое извлечение фактов о пользователе из разговора (имя, профессия, интересы и т.д.)
- **Заметки** — создание, просмотр, редактирование и удаление заметок с AI-генерацией тегов и описания
- **Задачи** — управление задачами с AI-определением приоритетов и дедлайнов
- **Семантический поиск** — поиск по всем данным (заметки, задачи, факты, диалоги) по смыслу, а не по ключевым словам
- **Напоминания** — создание напоминаний на естественном языке с поддержкой повторяющихся событий
- **Голосовые сообщения** — распознавание речи через Whisper API с автоматическим определением намерений
- **Intent Detection** — понимание естественного языка: "запиши заметку...", "покажи задачи", "напомни завтра..." — работает и текстом, и голосом
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
   |  (commands, |          | (auth, rate-limit|
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

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и описание возможностей |
| `/help` | Список всех команд |
| `/new` | Начать новый диалог (сбросить контекст сессии) |
| `/note` | Создать заметку (диалоговый режим или `/note <текст>`) |
| `/notes` | Список заметок (`/notes <тег>` — фильтр по тегу) |
| `/note_edit <id> <текст>` | Редактировать заметку |
| `/note_delete <id>` | Удалить заметку |
| `/task` | Создать задачу (диалоговый режим или `/task <описание>`) |
| `/tasks` | Активные задачи (`/tasks done` — выполненные) |
| `/task_done <id>` | Отметить задачу выполненной |
| `/task_progress <id>` | Перевести задачу в статус "в работе" |
| `/task_delete <id>` | Удалить задачу |
| `/remind` | Создать напоминание (диалоговый режим или `/remind <время> <текст>`) |
| `/reminders` | Список активных напоминаний |
| `/remind_delete <id>` | Удалить напоминание |
| `/search <запрос>` | Семантический поиск по всем данным |
| `/facts` | Просмотр сохраненных фактов о пользователе |
| `/forget <id>` | Удалить конкретный факт |
| `/forget_all` | Удалить все факты |
| `/profile` | Профиль пользователя |
| `/stats` | Статистика использования |
| `/settings` | Настройки бота |
| `/export <формат>` | Экспорт данных (json, csv, md, notion) |
| `/cancel` | Отмена текущей операции |

## Голосовые сообщения

Бот принимает голосовые сообщения и автоматически:
1. Распознает речь через OpenAI Whisper API
2. Определяет намерение пользователя (intent detection)
3. Выполняет действие или ведет диалог

Примеры голосовых команд:
- "Запиши заметку: купить молоко по дороге домой"
- "Покажи мои задачи"
- "Напомни завтра в 10 утра про встречу"
- "Найди информацию о React"

## Экспорт данных

### Notion
```
/export notion
```
Создает красиво оформленную страницу в Notion с разделами:
- Профиль пользователя (факты)
- Заметки с тегами и датами
- Задачи с чекбоксами и приоритетами
- Напоминания

При повторном экспорте — обновляет существующую страницу.

### Файлы
```
/export json   # Все данные в JSON
/export csv    # Заметки и задачи в CSV
/export md     # Все данные в Markdown
```
Файл отправляется как документ в чат.

## Структура проекта

```
AstraCompanionAIBot/
|-- bot/
|   |-- main.py                    # Точка входа
|   |-- config.py                  # Конфигурация из .env
|   |-- handlers/
|   |   |-- start.py               # /start, /help
|   |   |-- chat.py                # Текстовые сообщения + intent detection
|   |   |-- voice.py               # Голосовые сообщения
|   |   |-- notes.py               # /note, /notes, /note_edit, /note_delete
|   |   |-- tasks.py               # /task, /tasks, /task_done, /task_delete
|   |   |-- reminders.py           # /remind, /reminders, /remind_delete
|   |   |-- search.py              # /search
|   |   |-- facts.py               # /facts, /forget
|   |   |-- settings.py            # /settings, /stats, /profile
|   |   |-- export.py              # /export
|   |-- services/
|   |   |-- chat_service.py        # Диалог с AI + долговременная память
|   |   |-- note_service.py        # CRUD заметок + AI-теги
|   |   |-- task_service.py        # CRUD задач + AI-приоритеты
|   |   |-- reminder_service.py    # Напоминания + парсинг времени
|   |   |-- search_service.py      # Семантический поиск
|   |   |-- fact_extraction.py     # Извлечение фактов из диалога
|   |   |-- intent_service.py      # Определение намерений пользователя
|   |   |-- voice_service.py       # Транскрибация через Whisper
|   |   |-- embedding_service.py   # Векторизация текста
|   |   |-- notion_service.py      # Экспорт в Notion
|   |   |-- export_service.py      # Экспорт в файлы
|   |   |-- user_service.py        # Управление пользователями
|   |   |-- scheduler.py           # Планировщик напоминаний
|   |-- database/
|   |   |-- models.py              # SQLAlchemy модели
|   |   |-- postgres.py            # Подключение к PostgreSQL
|   |   |-- chromadb_client.py     # Клиент ChromaDB
|   |   |-- migrations/            # Alembic миграции
|   |-- middleware/
|   |   |-- auth.py                # Аутентификация (whitelist)
|   |   |-- rate_limiter.py        # Rate limiting
|   |   |-- encryption.py          # Шифрование данных
|   |   |-- error_handler.py       # Глобальная обработка ошибок
|   |-- utils/
|       |-- formatters.py          # Форматирование сообщений
|-- tests/                         # Юнит-тесты
|-- docker/
|   |-- Dockerfile
|   |-- docker-compose.yml
|-- .env.example
|-- requirements.txt
|-- alembic.ini
```

## Модели данных

### PostgreSQL

- **users** — пользователи (telegram_id, настройки, Notion page ID)
- **messages** — история диалогов (role, content, session_id)
- **notes** — заметки (content, summary, tags, chromadb_id)
- **tasks** — задачи (description, priority, status, deadline)
- **facts** — факты о пользователе (category, key, value, confidence)
- **reminders** — напоминания (text, trigger_at, is_recurring)

### ChromaDB (векторные коллекции)

- `user_{id}_notes` — векторы заметок
- `user_{id}_tasks` — векторы задач
- `user_{id}_facts` — векторы фактов
- `user_{id}_messages` — векторы сообщений

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
| `BOT_ADMIN_IDS` | ID администраторов (через запятую) | — |
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
# Запуск тестов
pytest

# С покрытием
pytest --cov=bot --cov-report=term-missing
```

## Лицензия

Личный pet-проект для портфолио. Некоммерческое использование.

## Автор

Алексей Астафьев — [astaf.al.mi@gmail.com](mailto:astaf.al.mi@gmail.com)
