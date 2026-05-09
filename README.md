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
make podcast
```

Эта команда собирает посты, выбирает новости, пишет диалоговый LLM-сценарий,
озвучивает его через XTTS и добавляет фоновую музыку. Если нужно только
быстро проверить формат на коротком выпуске:

```bash
make podcast-preview
```

Если нужно сразу опубликовать готовый `audio.mp3` в Telegram-канал:

```bash
make podcast-publish
```

Для публикации нужен канал в `.env`:

```dotenv
TELEGRAM_PUBLISH_CHANNEL_ID=-1001234567890
PUBLISH_TELEGRAM_ON_FINAL=false
```

`TELEGRAM_PUBLISH_CHANNEL_ID` можно указать числовым id канала или username вида
`@my_channel`. Аккаунт Telethon должен иметь право публиковать в этом канале.
`PUBLISH_TELEGRAM_ON_FINAL=true` включает автопубликацию для обычного финального
запуска, но по умолчанию она выключена, чтобы тестовые выпуски не улетали случайно.
Уже готовый последний выпуск можно отправить отдельно:

```bash
make publish-latest
```

Если нужно только
сгенерировать сценарий по уже собранным постам:

```bash
make podcast-script
```

Перед долгой озвучкой можно проверить и при необходимости детерминированно
починить начало сценария:

```bash
make podcast-script-check
```

Если сценарий уже готов и нужно только заново озвучить последний выпуск:

```bash
make podcast-audio
```

Если голоса уже готовы и нужно только перемиксовать музыку/громкость:

```bash
make podcast-remix
```

После генерации в папке выпуска сохраняется `script_quality_report.json`:
баланс персонажей, наличие приветствия, обзора тем, переходов, финального
вывода и список редакторских исправлений.

Также сохраняются публикационные файлы:

```text
show_notes.md
episode_metadata.json
```

Быстро посмотреть последний выпуск:

```bash
make podcast-info
```

Длина выпуска и количество новостей настраиваются через `.env`:

```dotenv
FINAL_COLLECT_LIMIT=20
FINAL_POOL_LIMIT=50
FINAL_TOP_POSTS=5
```

`FINAL_COLLECT_LIMIT` задаёт, сколько последних постов читать с каждого
канала. `FINAL_POOL_LIMIT` задаёт размер пула для ранжирования. `FINAL_TOP_POSTS`
задаёт, сколько новостей попадёт в выпуск.

Разово можно переопределить через CLI:

```bash
python scripts/make_podcast.py --collect-limit 30 --pool-limit 100 --top 8 --with-music
```

С Silero-озвучкой через единое окружение проекта:

```bash
make setup
make final-silero
```

С LLM-сценарием, Silero-озвучкой и chill-подложкой:

```bash
make final-silero-llm-music
```

С LLM-сценарием:

```bash
python scripts/final_run.py --llm-profile final --with-audio
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

Показать объяснение score:

```bash
python scripts/rank_posts.py --limit 50 --top 10 --show-breakdown
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

Auto-select использует объяснимую эвристику: вовлечённость, свежесть, длину,
IT-релевантность, расследовательский потенциал и штрафы за рекламный или
низкосигнальный текст. Причины выбора записываются в `editor_note`.

Веса источников настраиваются в:

```text
config/source_weights.txt
```

Формат:

```text
xakep_ru=1.20
data_secrets=1.10
whackdoor=0.85
```

Значения выше `1.0` мягко усиливают источник, ниже `1.0` приглушают шумные
каналы. Веса применяются в `rank_posts.py`, `auto_select_posts.py` и
`final_run.py`.

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

Проверить, что LLM-сценарий готов для многоголосой озвучки:

```bash
make validate-script
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
| `nika` | Ника | Деврел / объясняющая ведущая | `baya` | задаёт человеческие вопросы, объясняет сложное проще, добавляет живость |
| `artem` | Артём | Архитектор | `aidar` | объясняет механику, риски, эксплуатацию и последствия для production |

## Как поменять персонажей или голоса

Профили персонажей лежат в:

```text
app/podcast/characters.py
```

В одном месте настроены роль, характер, стиль речи, примеры фраз, TTS-провайдер,
голос Silero и паузы после реплик.

Маппинг голосов и аудио-характер персонажей строится в:

```text
app/audio/voices.py
```

Там же настроены темп, pitch, громкость и паузы. После генерации Silero каждая
реплика проходит локальную ffmpeg-постобработку: trimming тишины, лёгкое
изменение высоты/скорости и loudness-normalize. Это делает персонажей менее
похожими друг на друга и убирает часть механической монотонности.

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
XTTS_MODEL_NAME=tts_models/multilingual/multi-dataset/xtts_v2
XTTS_LANGUAGE=ru
XTTS_VOICE_REFS_DIR=data/voices/xtts
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

Проект использует единое окружение `.venv` на Python 3.11. Это общий знаменатель
для Telegram/LLM-пайплайна, PyTorch, Silero и Coqui XTTS-v2.

```bash
make setup
make tts-sample-silero
```

`make setup` использует `uv`, ставит локальный Python 3.11 в кэш `uv`, создаёт
`.venv`, ставит обычные зависимости, CPU-сборку PyTorch и Coqui TTS. Старые
команды `make setup-tts` и `make setup-xtts` оставлены как совместимые алиасы,
но тоже используют это же `.venv`.

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

Проверить параметры готового аудио:

```bash
python scripts/audio_report.py data/audio/sample_podcast.wav
```

Для пакетного выпуска аудио-отчёт также сохраняется рядом с выпуском:

```text
data/episodes/<episode>/audio_report.json
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
.venv/bin/python scripts/make_tts_sample.py --with-music
```

Подложка генерируется локально через `ffmpeg`, без внешних треков и без
лицензионных зависимостей. Громкость регулируется через
`AUDIO_BACKGROUND_MUSIC_VOLUME` или аргумент `--music-volume`.

## Экспериментальная XTTS-v2 озвучка

XTTS-v2 может звучать естественнее Silero, но ему нужны референсные голоса.
Положите короткие чистые WAV-файлы с разрешёнными голосами:

```text
data/voices/xtts/mark.wav
data/voices/xtts/gleb.wav
data/voices/xtts/nika.wav
data/voices/xtts/artem.wav
```

Рекомендуемая длина референса: 6-20 секунд, без музыки и сильного шума.
Файлы в `data/voices/` игнорируются git.

Установка Coqui TTS:

```bash
make setup
```

Coqui TTS 0.22.x не поддерживает Python 3.12+, поэтому единое окружение проекта
собирается на Python 3.11.

При первом запуске XTTS-v2 нужно согласиться с условиями лицензии Coqui CPML.
Интерактивно модель спросит подтверждение сама. Для автоматического запуска
можно явно поставить переменную:

```bash
COQUI_TOS_AGREED=1 make tts-sample-xtts
```

Тест XTTS:

```bash
make tts-sample-xtts
```

Озвучить текущий сценарий через XTTS:

```bash
make audio-xtts-music
```

Полный выпуск через XTTS:

```bash
make final-xtts-llm-music
```

Можно переопределить пути к референсам через `.env`:

```dotenv
XTTS_GLEB_VOICE=data/voices/xtts/gleb_alt.wav
```

Если есть свой loop-файл, его можно указать так:

```bash
.venv/bin/python scripts/make_audio.py --provider silero --with-music --music-path data/audio/music/chill_loop.wav
```

Или через `.env`:

```dotenv
AUDIO_BACKGROUND_MUSIC=true
AUDIO_BACKGROUND_MUSIC_PATH=data/audio/music/chill_loop.wav
```

Результат:

```text
data/audio/latest_episode.wav
data/audio/latest_episode.mp3
```

## Очистка локальных данных

Чтобы начать новый прогон с чистого листа, можно удалить сгенерированные
выпуски, временное аудио и SQLite-базу новостей:

```bash
make clean-generated-dry-run
make clean-generated
```

Скрипт сохраняет настройки, список каналов, голоса и музыку:

```text
config/channels.txt
data/voices/
data/audio/music/
```

То же самое напрямую:

```bash
python scripts/clean_workspace.py
python scripts/clean_workspace.py --yes
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
