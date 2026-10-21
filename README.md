<div align="center">

<img src="assets/nikcast_cover_256.jpg" alt="Новости АйТи" width="128" height="128">

# Новости АйТи

**Новости за сутки. Разговор на утро.**

[![Tests](https://github.com/NikKurkov/it-podcast-bot/actions/workflows/tests.yml/badge.svg)](https://github.com/NikKurkov/it-podcast-bot/actions/workflows/tests.yml)
[![Release](https://img.shields.io/github/v/release/NikKurkov/it-podcast-bot)](https://github.com/NikKurkov/it-podcast-bot/releases/latest)

[Послушать выпуск](https://t.me/nik_podcast/153) · [Быстрый запуск](#установка) · [Настройки](#настройки) · [Архитектура](docs/architecture.md)

</div>

Утренний IT-подкаст на 10–15 минут из новостей ваших Telegram-каналов.
Несколько ИИ-ведущих обсуждают события, объясняют детали и спорят по существу.
Сценарий и речь создаются локально; готовый выпуск можно проверить и отправить
в канал вручную или по расписанию.

## Как это работает

```text
Telegram → отбор новостей → источники → диалог → озвучка → выпуск
```

- **Новости за сутки.** Сбор сообщений, отбор по редакционным критериям и учёт уже опубликованных тем.
- **Разные голоса и характеры.** Настраиваемый состав ведущих, стиль общения и произношение.
- **Источники под рукой.** Исходные посты, связанные статьи и отчёты сохраняются вместе со сценарием.
- **Локальная обработка.** Ollama или llama.cpp для текста, Silero или XTTS для речи. Платный API не требуется.

Длительность зависит от материала: нехватка новостей не заполняется вымышленными
подробностями. Автоматическая проверка помогает редактуре, но не заменяет её.
[Пример звучания](https://t.me/nik_podcast/153) подготовлен по отдельно проверенному
редакторскому сценарию.

## Установка

Нужны Python 3.11, `uv`, ffmpeg/ffprobe, systemd user manager, `choom`
из util-linux и локальный Ollama либо llama.cpp. Telegram API ID и API Hash
можно получить на [my.telegram.org](https://my.telegram.org).

```bash
cp .env.example .env
# Заполните Telegram API ID/API Hash и config/channels.txt.
make setup
make doctor
make collect
ollama pull qwen2.5:7b-instruct
ollama pull qwen2.5:3b-instruct
make ollama
make llm-check
```

`make setup` пересоздаёт `.venv` и устанавливает CPU-окружение. Команды
`setup-tts` и `setup-xtts` вызывают тот же установщик. Существующее GPU-окружение
сначала сохраните. Для установки зависимостей в готовую среду:

```bash
uv pip install --python .venv/bin/python -r requirements-dev.txt
uv pip check --python .venv/bin/python
```

Первый `make collect` предложит войти в Telegram. Фоновому запуску нужна
сохранённая сессия. Публикация использует этот аккаунт: у него должны быть
права отправки сообщений в `TELEGRAM_PUBLISH_CHANNEL_ID`.

## Выпуск и публикация

```bash
make podcast-preview  # сбор, сценарий и звук без отправки
make podcast-script   # сценарий из уже собранных постов
make podcast-audio    # озвучка последнего пакета
make podcast-remix    # новое сведение из готовой чистой речи
make podcast-check   # проверка сценария, файлов и длительности
make podcast-info

# Отправка проверенного пакета в Telegram:
.venv/bin/python scripts/publish_latest.py --episode <slug> --dry-run
.venv/bin/python scripts/publish_latest.py --episode <slug>
```

`make podcast-generate-and-publish` выполняет полный цикл с отправкой.
Квитанция `telegram_publish.json` запрещает повторную публикацию пакета;
для намеренного повтора есть `--republish`. Если соединение оборвалось после
отправки, сначала проверьте канал: сервер мог уже принять сообщение.

## Настройки

Полный пример — в [.env.example](.env.example).

| Настройка | Назначение |
| --- | --- |
| `config/channels.txt` | Каналы-источники |
| `PODCAST_EDITORIAL_BRIEF` | Аудитория и критерии отбора |
| `config/podcast_style.md` | Стиль разговора и общие редакционные правила |
| `PODCAST_PARTICIPANTS` | Состав ведущих; профили в `app/podcast/characters.py` |
| `PODCAST_TARGET_MINUTES` | Целевая длительность |
| `FINAL_COLLECT_LIMIT=0` | Сбор полного суточного окна |
| `FINAL_POOL_LIMIT`, `FINAL_TOP_POSTS` | Размер пула и максимум новостей |
| `LLM_MODEL`, `LLM_FAST_MODEL`, `LLM_FINAL_MODEL`, `LLM_CHUNKED_MODEL` | Модели этапов |
| `LLM_SCRIPT_TEMPERATURE` | Температура автора сценария |
| `TTS_PROVIDER`, `TTS_DEVICE`, `TTS_CPU_THREADS` | Провайдер, устройство и потоки синтеза |
| `SILERO_MODEL_ID`, `SILERO_MODEL_PATH` | Версия Silero и необязательный локальный пакет |
| `XTTS_*_VOICE` | Файлы голосов XTTS |
| `TTS_AUTO_PRONUNCIATION` | Подготовка иностранных фраз локальной моделью |
| `config/pronunciation_ru.txt` | Явные фонетические замены |
| `AUDIO_BACKGROUND_MUSIC_VOLUME` | Громкость музыки |

По умолчанию используется Silero на CPU. Перед использованием голосов и моделей
проверьте условия их лицензий; сведения о проверенных весах находятся
в [манифесте](docs/local-model-manifest.json).

## Источники и качество

Отбор использует полные тексты, а не списки компаний. Реплики проверяются
по сохранённым источникам; спорные утверждения направляются на исправление
и повторную проверку. Структура разговора и распределение участников зависят
от материала. При обрезанном ответе, неизвестном участнике или нерешённых
замечаниях генерация останавливается до озвучки.

Загрузчик исследует ссылки из постов; общего веб-поиска нет. Он проверяет
публичные адреса и редиректы, ограничивает размер ответа и время запроса.
Недоступные страницы помечаются явно. Получение статьи не означает независимого
подтверждения новости. Некоторые прокси несовместимы с закреплением IP.

Локальные модели могут пропускать фактические ошибки и давать ложные замечания.
Перед публикацией проверяйте источники и слушайте выпуск.
`LLM_SCENE_CRITIC_ENABLED` и `LLM_EPISODE_PLAN_ENABLED` — экспериментальные
этапы, выключенные по умолчанию; основная проверка утверждений остаётся включённой.

## Модели и память

```bash
make ollama       # ограниченная фоновая служба
make ollama-stop
make ollama-cpu   # явный CPU-режим в терминале
```

Лаунчер ограничивает сервер через systemd cgroup: по умолчанию 4 GiB RAM,
256 MiB swap и один запрос одновременно. Тяжёлые Make-команды и установленная
служба выпуска получают отдельный лимит 5 GiB. Прямой запуск Python вне службы
или Make не создаёт таких ограничений. GPU и другие приложения в эти лимиты
не входят. Перед TTS приложение освобождает локальную модель.

`OLLAMA_CONTEXT_LENGTH` должен совпадать с контекстом сервера.
Дополнительный кэш промптов и снимки контекста выключены по умолчанию.
При включении `OLLAMA_CONTEXT_CHECKPOINTS` учитывайте дополнительную RAM;
`OLLAMA_CHECKPOINT_MIN_STEP` задаёт шаг снимков.

Для прямого сервера задайте `LOCAL_LLM_ENGINE=llamacpp`, путь к GGUF через
`LLAMA_CPP_MODEL_PATH`, приватный `LLM_API_KEY` и одинаковый alias всех моделей.
Бинарник задаётся через `LLAMA_CPP_EXECUTABLE`; доступны параметры шаблона чата,
CUDA-библиотеки, GPU-слоёв, потоков, reasoning budget и сна при простое.
Нужна сборка с поддержкой этих параметров. Работа проверяется реальным запросом,
а не только доступностью порта.

## Пакеты и восстановление

В `data/episodes/<slug>/` сохраняются исходники, сценарий, отчёты, звук,
метаданные и квитанция публикации. `spoken_script.md` хранится отдельно
от исходного `llm_script.md`. Контрольные точки позволяют продолжить генерацию:

```bash
.venv/bin/python scripts/resume_episode_script.py --episode <path>
.venv/bin/python scripts/render_episode_audio.py --episode <path> --with-music
```

Смена исходников, промптов, модели или значимых настроек инвалидирует кэш.
Готовый или опубликованный пакет перед правками скопируйте в новый черновик.
Длительность измеряется по аудио; автоматически рассчитанные таймкоды приблизительны.

## Расписание и разработка

```bash
make podcast-scheduler-preview
make podcast-scheduler-install  # ежедневный запуск в 07:00 с публикацией
make scheduler-check
make backup
make lint
make test
```

Для установки без отправки:
`.venv/bin/python scripts/install_scheduler.py --no-publish`.
Логи — в `data/logs/scheduled_podcast.log`, итог запуска — в `latest_run_report.json`.

`app/` содержит логику приложения, `scripts/` — CLI, `tests/` — pytest.
Секреты, сессии, базы, модели и готовый звук исключены из Git.
SQLite копируется через online backup API с учётом WAL.

[Архитектура](docs/architecture.md) · [Ручной рабочий процесс](docs/mvp_workflow.md)
· [Правила разработки](AGENTS.md) · [Изменения](CHANGELOG.md)
