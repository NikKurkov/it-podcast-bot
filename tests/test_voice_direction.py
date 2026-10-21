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
