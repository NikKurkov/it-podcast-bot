# Architecture

## Current scope

The current project scope is the local MVP for collecting Telegram posts,
storing them in SQLite, inspecting the database, ranking posts with simple
heuristics, and exporting digest drafts.

LLM agents, text-to-speech, and publishing are intentionally out of scope for
this stage.

## Main modules

- `app/config/settings.py`: `.env` based configuration.
- `app/telegram_reader/`: Telethon client, channel config loading, and collector.
- `app/db/`: SQLAlchemy models, session setup, and repositories.
- `app/pipeline/daily_digest.py`: Markdown/JSON digest export.
- `app/pipeline/scoring.py`: non-LLM post ranking.
- `app/pipeline/filters.py`: local keyword exclusion rules.
- `scripts/`: CLI entrypoints for day-to-day work.

## Local state

Ignored local state:

- `.env`
- `data/it_podcast_bot.sqlite3`
- `data/sessions/`
- `data/logs/`
- `data/episodes/`
- `data/backups/`

This keeps secrets, Telegram sessions, and generated artifacts out of git.
