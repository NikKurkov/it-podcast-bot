# Repository Guidelines

## Project Structure & Module Organization

This Python project collects Telegram news and produces a local, multi-voice morning podcast.

- `app/pipeline/`: selection, source research, episode packages, and publication metadata.
- `app/llm/`: local model integration, context budgeting, and editable prompts.
- `app/audio/`: dialogue partitioning, speech providers, mixing, and audio inspection.
- `app/podcast/`: character profiles and non-destructive script checks.
- `app/db/` and `app/telegram_reader/`: persistence and collection.
- `scripts/`: CLI entry points; keep reusable logic in `app/`.
- `tests/`: pytest tests. `config/` contains editable editorial inputs; `assets/` contains artwork.
- `data/`: ignored databases, sessions, logs, models, and generated episodes.

## Build, Test, and Development Commands

Run commands from the repository root using Python 3.11.

- `uv pip install --python .venv/bin/python -r requirements-dev.txt`: install application and development dependencies into an existing environment.
- `make setup`: recreate `.venv` and install the full CPU speech environment using `uv`; preserve a working GPU environment before using it.
- `make lint`: run Ruff checks.
- `make test`: run pytest; `.venv/bin/python -m pytest tests/test_news_ranker.py -q` runs focused tests.
- `make doctor`: inspect local prerequisites, including Ollama and ffmpeg.
- `make podcast-script`: generate a script from collected posts without publication.
- `make podcast-check`: inspect the latest episode.

## Coding Style & Naming Conventions

Use four-space indentation, UTF-8, LF endings, `snake_case` functions/modules, and `PascalCase` classes. Follow existing type annotations. Ruff targets Python 3.11; the configured line length is 100. Keep protocol and model limits explicit. Preserve complete source text and editorial order. Express relevance through the configurable editorial brief, never vendor exceptions, topic blacklists, or canned dialogue.

## Testing Guidelines

Use `tests/test_<area>.py` and `test_<behavior>`. Pytest replaces workstation settings before database imports. Isolate SQLite databases and output paths; mock Telegram and model calls. Test source preservation, invalid model responses, duplicate publication, and real audio operations where appropriate. Run focused tests, then Ruff and the full suite. CI enforces both; no coverage percentage is configured.

## Commit & Pull Request Guidelines

History uses imperative subjects, such as `Improve podcast script text quality`. Keep commits focused. PRs should explain behavior changes, configuration, validation results, and relevant issues; include script/audio examples for output changes.

## Security & Configuration

Never commit or print `.env`, credentials, Telegram sessions, private posts, or databases. Publication sends real messages; scheduler installation changes recurring execution. Preserve unrelated working-tree changes and use isolated demo output when testing.
