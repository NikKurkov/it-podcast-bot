from app.utils.text import is_meaningful_text, normalize_text


def test_normalize_text_removes_extra_spaces() -> None:
    assert normalize_text("  hello   \n  world\t ") == "hello world"


def test_is_meaningful_text_returns_false_for_empty_text() -> None:
    assert is_meaningful_text(" \n\t ") is False
