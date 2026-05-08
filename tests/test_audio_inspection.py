from app.audio.inspection import _format_duration, _format_size


def test_format_duration() -> None:
    assert _format_duration(65.2) == "01:05"
    assert _format_duration(None) == "unknown duration"


def test_format_size() -> None:
    assert _format_size(512) == "512 B"
    assert _format_size(2048) == "2.0 KB"
    assert _format_size(2 * 1024 * 1024) == "2.0 MB"
    assert _format_size(None) == "unknown size"
