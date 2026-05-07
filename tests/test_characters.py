import pytest

from app.podcast.characters import (
    format_character_profiles_for_prompt,
    get_character_keys,
    get_character_profile,
    resolve_character_key,
)


def test_get_character_keys_contains_final_characters() -> None:
    assert get_character_keys() == ["mark", "gleb", "nika", "artem"]


def test_get_character_profile_returns_mark() -> None:
    assert get_character_profile("mark").name == "Марк"


def test_resolve_character_key_supports_russian_names() -> None:
    assert resolve_character_key("Марк") == "mark"
    assert resolve_character_key("Артем") == "artem"
    assert resolve_character_key("Артём") == "artem"
    assert resolve_character_key("artem") == "artem"


def test_resolve_character_key_unknown_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="Unknown character"):
        resolve_character_key("unknown")


def test_format_character_profiles_for_prompt_contains_all_names() -> None:
    prompt_context = format_character_profiles_for_prompt()

    assert "Марк" in prompt_context
    assert "Глеб" in prompt_context
    assert "Ника" in prompt_context
    assert "Артём" in prompt_context
