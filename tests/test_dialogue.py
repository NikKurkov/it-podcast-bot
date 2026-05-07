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
