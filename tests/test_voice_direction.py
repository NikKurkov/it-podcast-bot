from app.audio.voice_direction import apply_voice_direction


def test_apply_voice_direction_marks_transition() -> None:
    line = apply_voice_direction(
        "mark",
        "А вот дальше история про GitHub и доступность репозиториев.",
        base_pause_after_ms=500,
    )

    assert line.emotion == "transition"
    assert line.pause_after_ms >= 820


def test_apply_voice_direction_marks_rundown() -> None:
    line = apply_voice_direction(
        "nika",
        "Сегодня в выпуске: GitHub, вайбкодинг и безопасность аккаунтов.",
        base_pause_after_ms=430,
    )

    assert line.emotion == "rundown"
    assert line.pause_after_ms >= 760


def test_apply_voice_direction_marks_human_aside() -> None:
    line = apply_voice_direction(
        "gleb",
        "Глеб, клавиатуру слышно, будь здоров.",
        base_pause_after_ms=520,
    )

    assert line.emotion == "aside"
    assert line.pause_after_ms <= 380
