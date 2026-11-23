import pytest

from app.audio.voice_direction import apply_voice_direction


@pytest.mark.parametrize(
    "text",
    [
        "Теперь клиент может продолжить работу.",
        "Сегодня в выпуске обсуждаем новости.",
        "Подожди, это лишь предположение.",
        "Следом за обновлением вышло исправление.",
        "Вывод ещё не подтверждён.",
    ],
)
def test_story_words_do_not_create_sound_effects_or_long_pauses(text):
    line = apply_voice_direction("nika", text, base_pause_after_ms=250)
    assert line.text == text
    assert line.emotion is None
    assert line.pause_after_ms == 250


def test_quick_exchange_has_a_shorter_pause_than_a_long_explanation():
    short = apply_voice_direction("nika", "На всех версиях?", base_pause_after_ms=520)
    long = apply_voice_direction(
        "nika",
        "В этом выпуске разработчик проверил только работу бета-версии на одном устройстве.",
        base_pause_after_ms=520,
    )
    assert short.pause_after_ms == 300
    assert long.pause_after_ms == 520
