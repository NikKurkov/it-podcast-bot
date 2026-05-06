from app.utils.hashing import make_text_hash


def test_same_text_after_normalization_has_same_hash() -> None:
    assert make_text_hash("hello   world") == make_text_hash("  hello world\n")


def test_different_text_has_different_hash() -> None:
    assert make_text_hash("hello world") != make_text_hash("hello python")
