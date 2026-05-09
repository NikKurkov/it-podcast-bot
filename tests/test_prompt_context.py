from datetime import datetime

from app.podcast.prompt_context import build_scriptwriter_context, format_russian_episode_date


def test_format_russian_episode_date() -> None:
    assert format_russian_episode_date(datetime(2026, 5, 9, 12, 0)) == "девятое мая"


def test_build_scriptwriter_context_contains_episode_date() -> None:
    context = build_scriptwriter_context()

    assert "character_profiles" in context
    assert "episode_date_ru" in context
