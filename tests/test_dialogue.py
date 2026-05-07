from app.audio.dialogue import script_to_dialogue_lines


def test_script_to_dialogue_lines_parses_explicit_speakers() -> None:
    lines = script_to_dialogue_lines(
        """
boris: Коллеги, начнём.
lena: Отлично, я готова.
max: Давайте разберём контекст.
""",
    )

    assert [line.speaker for line in lines] == ["boris", "lena", "max"]
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

    assert [line.speaker for line in lines] == ["boris", "lena"]
    assert lines[1].text == "Второй абзац с акцентом."
