<div align="center">

<img src="assets/nikcast_cover_256.jpg" alt="Новости АйТи" width="128" height="128">

# Новости АйТи

**Новости из ваших Telegram-каналов обсуждают ИИ-ведущие**

[![Tests](https://github.com/NikKurkov/it-podcast-bot/actions/workflows/tests.yml/badge.svg)](https://github.com/NikKurkov/it-podcast-bot/actions/workflows/tests.yml)
[![Release](https://img.shields.io/github/v/release/NikKurkov/it-podcast-bot)](https://github.com/NikKurkov/it-podcast-bot/releases/latest)

[Послушать выпуск](https://t.me/nik_podcast) · [Docker](#docker) · [Запустить без Docker](#быстрый-запуск)

</div>

Вы указываете каналы, а бот собирает новости за сутки и делает выпуск. Сценарий и звук создаются на вашем компьютере. Готовый выпуск можно прослушать и отправить в Telegram вручную или по расписанию.

Исходные посты остаются рядом со сценарием, чтобы можно было сверить факты. Если тему так и не удалось подтвердить, бот пропускает её и продолжает сборку. После сбоя можно продолжить с сохранённых сцен.

## Docker

Для запуска нужен Docker Compose на Linux x86-64. Сценарий и озвучка собираются на CPU. В первый раз Docker скачает образы, а Ollama и Silero загрузят модели.

```bash
cp .env.example .env.docker
mkdir -p data
export PODCAST_UID="$(id -u)" PODCAST_GID="$(id -g)"
```

Впишите Telegram API ID и API Hash в `.env.docker`. Каналы, из которых нужно брать новости, перечислите в `config/channels.txt`.

```bash
docker compose up -d --wait ollama
docker compose exec ollama ollama pull qwen2.5:7b-instruct
docker compose run --rm --build podcast scripts/collect_posts.py --limit 10
docker compose run --rm podcast
```

В первый раз `collect_posts.py` попросит войти в Telegram. Последняя команда соберёт короткий выпуск и положит сценарий и MP3 в `data/episodes/`. Отправка в Telegram отключена.

Для выпуска обычной длины запустите `docker compose run --rm podcast scripts/make_podcast.py --with-music`. Когда закончите, остановите Ollama командой `docker compose stop ollama`.

Если у вас уже есть база и выпуски в `data/`, для пробы можно создать отдельную папку и указать её в переменной `PODCAST_DATA_DIR`.

Если Telegram работает через SOCKS-прокси на вашем компьютере, в `.env.docker` укажите его адрес через `host.docker.internal`. Например, `TELEGRAM_PROXY_URL=socks5://host.docker.internal:2080`. Прокси должен принимать подключения из Docker.

## Быстрый запуск

На Linux нужны Python 3.11, `uv`, ffmpeg, systemd и Ollama.

```bash
cp .env.example .env
```

Укажите Telegram API ID и API Hash в `.env`, а каналы для сбора новостей — в `config/channels.txt`.

```bash
make setup
make ollama
ollama pull qwen2.5:7b-instruct
ollama pull qwen2.5:3b-instruct
make llm-check
make collect
make doctor
make podcast-preview
```

При первом `make collect` нужно войти в Telegram. `make podcast-preview` соберёт пробный выпуск с аудио без отправки. Файлы будут в `data/episodes/`.

`make setup` пересоздаёт `.venv` для CPU. В существующем окружении можно установить зависимости командой `uv pip install --python .venv/bin/python -r requirements-dev.txt`.

## Команды

| Команда | Что делает |
| --- | --- |
| `make podcast-script` | Сценарий из уже собранных новостей |
| `make podcast-audio` | Озвучка последнего сценария |
| `make podcast-check` | Проверка сценария и аудио |
| `make podcast-publish` | Отправка последнего готового выпуска |
| `make podcast-generate-and-publish` | Полный цикл с отправкой |
| `make podcast-scheduler-preview` | Показ настроек расписания |
| `make podcast-scheduler-install` | Ежедневная генерация и публикация в 07:00 |

Для отправки задайте `TELEGRAM_PUBLISH_CHANNEL_ID` и дайте подключённому аккаунту право публиковать в канале. Перед отправкой прослушайте выпуск и проверьте спорные утверждения по источникам.

## Настройки и документация

Пример настроек есть в [`.env.example`](.env.example). Стиль реплик задаётся в [`config/podcast_style.md`](config/podcast_style.md), произношение — в [`config/pronunciation_ru.txt`](config/pronunciation_ru.txt). По умолчанию речь озвучивает Silero на CPU. Доступны XTTS для речи и llama.cpp для сценария.

[Ручная сборка и публикация](docs/mvp_workflow.md) · [Архитектура и память](docs/architecture.md) · [Модели](docs/local-model-manifest.json) · [Изменения](CHANGELOG.md)
