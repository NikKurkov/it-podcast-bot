from app.audio.dialogue import script_to_dialogue_lines


def test_script_to_dialogue_lines_parses_explicit_speakers() -> None:
    lines = script_to_dialogue_lines(
        """
mark: Коллеги, начнём.
nika: Отлично, я готова.
artem: Давайте разберём контекст.
""",
    )

    assert [line.speaker for line in lines] == ["mark", "nika", "artem"]
    assert lines[0].text == "Коллеги, начнём."


def test_script_to_dialogue_lines_falls_back_to_round_robin_markdown() -> None:
    lines = script_to_dialogue_lines(
        """
# Заголовок

Первый абзац новости.

Второй абзац с **акцентом**.

[Звуковой эффект]
""",
    )

    assert [line.speaker for line in lines] == ["mark", "gleb"]
    assert lines[1].text == "Второй абзац с акцентом."


def test_script_to_dialogue_lines_parses_russian_speaker_names() -> None:
    lines = script_to_dialogue_lines(
        """
Марк: Давайте восстановим цепочку событий.
Ника: А если по-человечески?
Артём: Важна воспроизводимость сборки.
""",
    )

    assert [line.speaker for line in lines] == ["mark", "nika", "artem"]


def test_script_to_dialogue_lines_splits_long_explicit_lines_for_tts() -> None:
    long_text = " ".join(["очень длинная реплика"] * 20)
    lines = script_to_dialogue_lines(f"mark: {long_text}")

    assert len(lines) > 1
    assert {line.speaker for line in lines} == {"mark"}
    assert all(len(line.text) <= 170 for line in lines)


def test_script_to_dialogue_lines_does_not_leave_tiny_tail_chunk() -> None:
    text = (
        "Anker выпустила флагманские наушники soundcore Liberty 5 Pro и Pro Max "
        "В новинках впервые используется собственный ИИ-чип, который обеспечивает "
        "вдвое более мощное шумоподавление."
    )

    lines = script_to_dialogue_lines(f"nika: {text}")

    assert all(len(line.text) <= 170 for line in lines)
    assert len(lines[-1].text) >= 45
    assert " ".join(line.text for line in lines) == text
    assert not any(line.text == "обеспечивает." or line.text == "обеспе." for line in lines)


def test_script_to_dialogue_lines_skips_service_lines_and_cleans_symbols() -> None:
    lines = script_to_dialogue_lines(
        """
Generated at: 2026-05-07T16:36:48

Editor note: Auto-selected

⚡️ Новость от @channel #123 с маркером • и ссылкой https://example.com

Source: https://t.me/channel/123
""",
    )

    assert len(lines) == 1
    assert "Generated at" not in lines[0].text
    assert "Editor note" not in lines[0].text
    assert "Source" not in lines[0].text
    assert "https://" not in lines[0].text
    assert "@" not in lines[0].text


def test_script_to_dialogue_lines_normalizes_russian_dates_for_tts() -> None:
    lines = script_to_dialogue_lines(
        """
mark: Добрый день, сегодня 09 мая, и вы слушаете НикКаст.
nika: Проверим релизы за 1 июня и 31 декабря.
""",
    )

    assert "девятое мая" in lines[0].text
    assert "первое июня" in lines[1].text
    assert "тридцать первое декабря" in lines[1].text


def test_split_long_text_preserves_sentence_before_long_sentence() -> None:
    from app.audio.dialogue import _split_long_text

    text = "Важный факт. " + " ".join(["Подробности следующей новости"] * 20) + ". Конец."
    chunks = _split_long_text(text, max_chars=80)
    assert " ".join(chunks) == text


def test_dialogue_cleaning_preserves_technical_notation():
    lines = script_to_dialogue_lines("mark: C++, C#, v3.11, 5%, /api/v2 и a+b=c.")
    assert lines[0].text == "C++, C#, v3.11, 5%, /api/v2 и a+b=c."


def test_internal_tts_split_does_not_add_a_turn_pause_mid_sentence():
    from app.audio.dialogue import script_to_dialogue_lines

    text = " ".join(["совместимость"] * 40) + "."
    lines = script_to_dialogue_lines("nika: " + text)
    assert len(lines) > 1
    assert all(
        line.pause_after_ms <= 60
        for line in lines[:-1]
        if not line.text.endswith((".", "?", "!", "…"))
    )
    assert " ".join(line.text for line in lines) == text
