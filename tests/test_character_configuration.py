import pytest

from app.config.settings import settings
from app.podcast import characters


def test_active_cast_changes_generation_without_breaking_saved_speakers(monkeypatch):
    monkeypatch.setattr(settings, "podcast_participants", "Марк, Ника,mark")
    assert characters.get_active_character_keys() == ["mark", "nika"]
    prompt = characters.format_character_profiles_for_prompt()
    assert "mark:" in prompt and "nika:" in prompt
    assert "gleb:" not in prompt and "artem:" not in prompt
    assert characters.resolve_character_key("Артём") == "artem"


@pytest.mark.parametrize("value", ["", "unknown-host"])
def test_invalid_active_cast_fails_explicitly(monkeypatch, value):
    monkeypatch.setattr(settings, "podcast_participants", value)
    with pytest.raises(ValueError):
        characters.get_active_character_keys()
