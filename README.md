<div align="center">

<img src="assets/nikcast_cover_256.jpg" alt="Новости АйТи" width="128" height="128">

# Новости АйТи

**Новости из ваших Telegram-каналов обсуждают ИИ-ведущие**

[![Tests](https://github.com/NikKurkov/it-podcast-bot/actions/workflows/tests.yml/badge.svg)](https://github.com/NikKurkov/it-podcast-bot/actions/workflows/tests.yml)
[![Release](https://img.shields.io/github/v/release/NikKurkov/it-podcast-bot)](https://github.com/NikKurkov/it-podcast-bot/releases/latest)

[Послушать выпуск](https://t.me/nik_podcast) · [Docker](#docker) · [Без Docker](#без-docker)

</div>

Вы указываете каналы, а бот собирает новости за сутки и делает выпуск. Сценарий и звук создаются на вашем компьютере. Готовый выпуск можно прослушать и отправить в Telegram вручную или по расписанию.

Исходные посты остаются рядом со сценарием, чтобы можно было сверить факты. Если тему так и не удалось подтвердить, бот пропускает её и продолжает сборку. После сбоя можно продолжить с сохранённых сцен.

## Быстрый запуск

Откройте папку проекта и выберите способ запуска. Чтобы собирать новости из своих каналов, перечислите их в `config/channels.txt`. При первом запуске понадобится войти в Telegram. Сценарий и MP3 появятся в `data/episodes/`. Пробный выпуск остаётся на компьютере.

### Docker

На Linux x86-64 нужны Docker Compose и Make.

```bash
cp .env.example .env.docker
```

Впишите Telegram API ID и API Hash в `.env.docker`, затем выполните команду.

```bash
make docker-quickstart
```

Первая сборка скачает образы и модели.

### Без Docker

На Linux нужны Make, `uv`, ffmpeg, systemd и запущенный Ollama на порту 11434.

```bash
cp .env.example .env
```

Впишите Telegram API ID и API Hash в `.env`, затем выполните две команды.

```bash
make setup
make quickstart
```

`make setup` создаёт окружение Python. Если оно уже настроено, сразу запускайте `make quickstart`.

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

Для отдельной папки с данными Docker задайте `PODCAST_DATA_DIR` в окружении перед запуском Make. Если Telegram нужен SOCKS-прокси на хосте, укажите его в `.env.docker`, например `TELEGRAM_PROXY_URL=socks5://host.docker.internal:2080`.

[Ручная сборка и публикация](docs/mvp_workflow.md) · [Архитектура и память](docs/architecture.md) · [Модели](docs/local-model-manifest.json) · [Изменения](CHANGELOG.md)
