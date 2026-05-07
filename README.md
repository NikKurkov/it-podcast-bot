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

Полный локальный дневной прогон:

```bash
python scripts/daily_run.py --collect-limit 20 --digest-limit 10
```

Полный локальный выпуск одной командой:

```bash
python scripts/final_run.py --collect-limit 20 --top 5 --with-audio
```

С Silero-озвучкой через отдельное TTS-окружение:

```bash
make setup-tts
make final-silero
```

С LLM-сценарием:

```bash
python scripts/final_run.py --collect-limit 20 --top 5 --llm-profile final --with-audio
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

## Редакторская разметка

Выбрать пост для выпуска:

```bash
python scripts/edit_post.py --id 1 --select --category "top news" --note "Хорошо для вступления"
```

Отклонить пост:

```bash
python scripts/edit_post.py --id 2 --reject --note "Не IT"
```

Посмотреть выбранные посты:

```bash
python scripts/list_selected_posts.py
```

Автоматически выбрать топ постов:

```bash
python scripts/auto_select_posts.py --top 5 --reset-existing
```

Сделать простой черновик сценария из выбранных постов:

```bash
python scripts/make_script_draft.py
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

Экспортировать только выбранные редактором посты:

```bash
python scripts/make_digest.py --only-selected --ranked --limit 20
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

Удалить черновик выпуска:

```bash
python scripts/delete_episode_draft.py 1
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

Тесты также запускаются в GitHub Actions при пуше в `main`.

Если используете `make`, основные команды доступны так:

```bash
make test
make collect
make stats
make list
make selected
make rank
make csv
make digest
make script
make episode
make episodes
make validate
```

В репозитории есть `.editorconfig`, чтобы IDE держали единый стиль отступов и
переводов строк.

## Локальный LLM

Рекомендуемая модель для текущего железа:

```text
qwen2.5:7b-instruct
```

Установите Ollama и скачайте модель:

```bash
# Arch/CachyOS:
sudo pacman -S ollama

ollama pull qwen2.5:7b-instruct
```

Настройки в `.env`:

```dotenv
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=qwen2.5:7b-instruct
```

Проверить доступность локального LLM:

```bash
make llm-check
```

Для GTX 1070 Ti текущий Ollama/CUDA может падать. Рабочий режим для этой машины:

```bash
make ollama-cpu
```

Оставьте эту команду запущенной в отдельном терминале.

Сгенерировать сценарий через локальную модель:

```bash
make script
make llm-script
```

Сценарий сразу в формате диалога для четырёх голосов:

```bash
make llm-dialogue-script
```

Быстрый и финальный профили:

```bash
ollama pull qwen2.5:3b-instruct
make llm-script-fast
make llm-script-final
```

Результат:

```text
data/episodes/latest_llm_script.md
```

## Пакет выпуска

Создать отдельную папку выпуска из выбранных постов:

```bash
python scripts/make_episode_package.py --limit 10
```

С LLM-сценарием:

```bash
python scripts/make_episode_package.py --limit 10 --llm-profile final
```

С локальной Silero-озвучкой и LLM-сценарием в формате диалога:

```bash
make episode-package-silero
```

Структура:

```text
data/episodes/YYYY-MM-DD_HHMMSS/
├── digest.md
├── selected_posts.json
├── script_draft.md
├── llm_script.md
├── audio.wav
├── audio.mp3
└── metadata.json
```

## Локальная озвучка подкаста

Основной локальный TTS-провайдер для русской озвучки: Silero TTS.

## Персонажи подкаста

Формат выпуска: разговорное техно-расследование на 4 голоса.

| character_key | имя | роль | голос Silero | функция |
| --- | --- | --- | --- | --- |
| `mark` | Марк | Следователь / ведущий-аналитик | `eugene` | держит структуру, восстанавливает цепочку событий, делает выводы |
| `gleb` | Глеб | Старый Хакер | `aidar` | снижает хайп, добавляет инженерный скепсис и сухой юмор |
| `nika` | Ника | Деврел / объясняющая ведущая | `xenia` | задаёт человеческие вопросы, объясняет сложное проще, добавляет живость |
| `artem` | Артём | Архитектор | `aidar` | объясняет механику, риски, эксплуатацию и последствия для production |

## Как поменять персонажей или голоса

Профили персонажей лежат в:

```text
app/podcast/characters.py
```

В одном месте настроены роль, характер, стиль речи, примеры фраз, TTS-провайдер,
голос Silero и паузы после реплик.

Маппинг голосов для аудио строится из этих профилей в:

```text
app/audio/voices.py
```

Тестовый сценарий для локальной озвучки лежит в:

```text
scripts/make_tts_sample.py
```

Настройки `.env`:

```dotenv
TTS_PROVIDER=silero
TTS_OUTPUT_DIR=data/audio
TTS_SAMPLE_RATE=48000
TTS_DEVICE=cpu
AUDIO_BACKGROUND_MUSIC=false
AUDIO_BACKGROUND_MUSIC_VOLUME=0.16
```

Проверить `ffmpeg`:

```bash
ffmpeg -version
```

Установить Python-зависимости:

```bash
pip install -r requirements.txt
```

Для реального Silero нужен PyTorch. Если `torch` недоступен для текущего Python,
создайте отдельный Python 3.12 venv для TTS и установите PyTorch туда.
При первом запуске Silero может скачать модель через `torch.hub`.

`torch` намеренно не закреплён в `requirements.txt`, потому что сборка зависит
от версии Python, CPU/GPU и платформы. Остальные лёгкие зависимости TTS уже в
`requirements.txt`.

На этой машине основной проект может жить в `.venv` на свежем Python, а Silero
удобнее запускать из отдельного CPU-only окружения:

```bash
make setup-tts
make tts-sample-silero
```

`make setup-tts` использует `uv`, ставит локальный Python 3.12 в кэш `uv`,
создаёт `.venv-tts` внутри проекта и ставит CPU-сборку PyTorch. Это не трогает
основной `.venv`.

Тестовая многоголосая озвучка:

```bash
python scripts/make_tts_sample.py
```

Результат:

```text
data/audio/sample_episode/001_mark.wav
data/audio/sample_episode/002_nika.wav
data/audio/sample_episode/003_gleb.wav
data/audio/sample_episode/004_artem.wav
data/audio/sample_podcast.wav
```

Сделать Silero-озвучку текущего сценария `latest_llm_script.md`:

```bash
make audio-silero
```

Добавить тихую процедурную chill-подложку:

```bash
make audio-silero-music
```

Для тестового выпуска:

```bash
.venv-tts/bin/python scripts/make_tts_sample.py --with-music
```

Подложка генерируется локально через `ffmpeg`, без внешних треков и без
лицензионных зависимостей. Громкость регулируется через
`AUDIO_BACKGROUND_MUSIC_VOLUME` или аргумент `--music-volume`.

Результат:

```text
data/audio/latest_episode.wav
data/audio/latest_episode.mp3
```

В проекте также осталась простая legacy-озвучка через `espeak-ng` как явный
fallback:

```bash
python scripts/make_audio.py --provider espeak
```

Вход:

```text
data/episodes/latest_llm_script.md
```

Результат:

```text
data/audio/latest_episode.wav
data/audio/latest_episode.mp3
```
