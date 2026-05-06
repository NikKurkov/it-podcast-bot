# it-podcast-bot

Бот для будущей автоматизации IT-подкаста: он будет читать Telegram-каналы с
новостями, сохранять посты, собирать дайджест, готовить сценарий, озвучивать и
публиковать выпуск.

Сейчас реализован первый MVP: сбор последних текстовых сообщений из списка
Telegram-каналов через пользовательский Telegram-аккаунт и сохранение в локальную
SQLite-базу без дублей.

## Что уже есть

- конфигурация через `.env`;
- список Telegram-каналов;
- Telethon-клиент с локальной сессией;
- модели SQLAlchemy `SourceChannel` и `TelegramPost`;
- SQLite-хранилище;
- CLI-команда сбора постов;
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
```

## Запуск сбора постов

```bash
python scripts/collect_posts.py --limit 20
```

Без `--limit` будет использовано значение `DEFAULT_LIMIT_PER_CHANNEL` из `.env`.

SQLite-база по умолчанию лежит здесь:

```text
data/it_podcast_bot.sqlite3
```

## Как поменять список каналов

Основной список находится в:

```text
app/telegram_reader/channels.py
```

Пример:

```python
CHANNELS = [
    "durov",
    "pythonetc",
]
```

Можно также временно переопределить список через `.env`:

```dotenv
TELEGRAM_CHANNELS=durov,pythonetc
```

## Тесты

```bash
pytest
```
