# it-podcast-bot

Бот для будущей автоматизации IT-подкаста: он будет читать Telegram-каналы с
новостями, сохранять посты, собирать дайджест, готовить сценарий, озвучивать и
публиковать выпуск.

Сейчас реализован первый MVP: сбор последних текстовых сообщений из списка
Telegram-каналов через пользовательский Telegram-аккаунт и сохранение в локальную
SQLite-базу без дублей.

Дополнительные заметки:

- [MVP workflow](docs/mvp_workflow.md)
- [Architecture](docs/architecture.md)

## Что уже есть

- конфигурация через `.env`;
- список Telegram-каналов в отдельном конфиг-файле;
- Telethon-клиент с локальной сессией;
- модели SQLAlchemy `SourceChannel` и `TelegramPost`;
- SQLite-хранилище;
- CLI-команда сбора постов;
- CLI-команды просмотра базы и экспорта простого дайджеста;
- минимальные тесты для нормализации текста и хэширования.

## Telegram API ID и API Hash

1. Откройте https://my.telegram.org.
2. Войдите под своим Telegram-аккаунтом.
3. Перейдите в `API development tools`.
4. Создайте приложение.
5. Скопируйте `api_id` и `api_hash` в `.env`.

При первом запуске Telethon попросит номер телефона, код из Telegram и, если
включена двухфакторная защита, пароль. После успешной авторизации локальная
сессия сохранится в `data/sessions/` и повторно вводить код обычно не нужно.

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Заполните в `.env`:

```dotenv
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=your_api_hash_here
TELEGRAM_SESSION_NAME=it_podcast_bot
DATABASE_URL=sqlite:///data/it_podcast_bot.sqlite3
LOG_LEVEL=INFO
DEFAULT_LIMIT_PER_CHANNEL=20
TELEGRAM_CHANNELS_FILE=config/channels.txt
EXCLUDE_KEYWORDS_FILE=config/exclude_keywords.txt
```

Если Telegram недоступен напрямую, можно указать SOCKS-прокси:

```dotenv
TELEGRAM_PROXY_URL=socks5://127.0.0.1:2080
```

Для прокси с авторизацией:

```dotenv
TELEGRAM_PROXY_URL=socks5://username:password@127.0.0.1:2080
```

## Запуск сбора постов

```bash
python scripts/collect_posts.py --limit 20
```

Без `--limit` будет использовано значение `DEFAULT_LIMIT_PER_CHANNEL` из `.env`.
Можно собрать один канал:

```bash
python scripts/collect_posts.py --channel whackdoor --limit 10
```

SQLite-база по умолчанию лежит здесь:

```text
data/it_podcast_bot.sqlite3
```

Бэкап текущей SQLite-базы:

```bash
python scripts/backup_db.py
```

Проверка качества данных:

```bash
python scripts/validate_db.py
```

## Просмотр базы

Проверка локальной настройки:

```bash
python scripts/check_setup.py
```

Проверка сохранённой Telegram-сессии без запуска интерактивной авторизации:

```bash
python scripts/check_setup.py --telegram
```

Статистика:

```bash
python scripts/db_stats.py
```

Отчёт по источникам:

```bash
python scripts/source_report.py
```

Последние посты:

```bash
python scripts/list_posts.py --limit 10
```

Фильтр по каналу:

```bash
python scripts/list_posts.py --channel whackdoor --limit 10
```

Полная запись поста:

```bash
python scripts/show_post.py --id 1
python scripts/show_post.py --channel whackdoor --message-id 28245
```

Ранжирование постов простой эвристикой без LLM:

```bash
python scripts/rank_posts.py --limit 50 --top 10
```

CSV-экспорт для ручного анализа:

```bash
python scripts/export_posts_csv.py --limit 100
```

## Экспорт дайджеста без LLM

Markdown:

```bash
python scripts/make_digest.py --limit 50 --format markdown
```

JSON:

```bash
python scripts/make_digest.py --limit 50 --format json
```

Только необработанные посты с пометкой после успешного экспорта:

```bash
python scripts/make_digest.py --only-unprocessed --mark-processed --limit 50
```

Сбросить флаг обработки для всех постов:

```bash
python scripts/mark_posts.py unprocessed --all
```

Фильтр по дате:

```bash
python scripts/make_digest.py --since 2026-05-06 --until 2026-05-06
```

Простые фильтры без LLM:

```bash
python scripts/make_digest.py --min-views 5000 --contains Python --exclude реклама
```

Экспорт с сортировкой по простому score:

```bash
python scripts/make_digest.py --ranked --limit 20
```

Исключить посты по словам из `config/exclude_keywords.txt`:

```bash
python scripts/make_digest.py --use-exclude-keywords --ranked --limit 20
```

По умолчанию файлы создаются в `data/episodes/`.

## Черновик выпуска без LLM

Создать локальный черновик выпуска из лучших постов:

```bash
python scripts/make_episode_draft.py --limit 10
```

Посмотреть созданные черновики:

```bash
python scripts/list_episode_drafts.py
```

## Как поменять список каналов

Основной список находится в:

```text
config/channels.txt
```

Пример:

```text
durov
pythonetc
```

Можно также временно переопределить список через `.env`:

```dotenv
TELEGRAM_CHANNELS=durov,pythonetc
```

Список можно посмотреть и изменить командами:

```bash
python scripts/channels.py list
python scripts/channels.py add new_channel
python scripts/channels.py remove old_channel
```

## Тесты

```bash
pytest
```

Если используете `make`, основные команды доступны так:

```bash
make test
make collect
make stats
make list
make rank
make csv
make digest
make episode
make episodes
make validate
```
