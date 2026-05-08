import pytest

from app.audio.postprocess import _atempo_filters


def test_atempo_filters_keeps_ffmpeg_values_in_supported_range() -> None:
    filters = _atempo_filters(3.2)

    values = [float(item.split("=")[1]) for item in filters]
    assert all(0.5 <= value <= 2.0 for value in values)
    assert pytest.approx(values[0] * values[1]) == 3.2


def test_atempo_filters_rejects_zero_tempo() -> None:
    with pytest.raises(ValueError, match="tempo"):
        _atempo_filters(0)
