import pytest

from app.podcast.script_validation import (
    format_validation_report,
    repair_dialogue_script_text,
    validate_dialogue_script,
)


def test_validate_dialogue_script_accepts_final_characters() -> None:
    result = validate_dialogue_script(
        """
mark: Сегодня смотрим, как новость превращается в практический риск для команды.
gleb: Я видел похожие истории, и обычно слабое место находится в эксплуатации.
nika: А если по-человечески?
artem: Здесь важно проверить права доступа и план отката.
""",
    )

    assert result.has_errors is False
    assert result.has_blocking_issues is False
    assert result.lines_count == 4
    assert result.speakers == ["mark", "gleb", "nika", "artem"]


def test_validate_dialogue_script_reports_legacy_character() -> None:
    result = validate_dialogue_script("boris: Старый формат.")

    assert result.has_errors is True
    assert result.has_blocking_issues is True
    assert any("boris" in issue.message for issue in result.issues)


def test_validate_dialogue_script_warns_when_character_is_missing():
    result = validate_dialogue_script("mark: Один.\nnika: Два.", require_all_characters=True)
    assert not result.has_errors
    assert not result.has_blocking_issues
    assert any(issue.code == "missing_character" for issue in result.issues)


def test_validate_dialogue_script_blocks_markdown_separator() -> None:
    result = validate_dialogue_script(
        """
mark: Риск не в анонсе, а в зависимости команды от внешнего сервиса.
---
nika: Практический вопрос в том, где запасной путь.
gleb: Я видел похожие истории.
artem: Команде нужен план отката и проверка доступа.
""",
    )

    assert result.has_blocking_issues is True
    assert any(issue.code == "non_dialogue_text" for issue in result.issues)


def test_format_validation_report_ok() -> None:
    result = validate_dialogue_script(
        """
mark: Один.
gleb: Два.
nika: Три.
artem: Четыре.
""",
    )

    assert format_validation_report(result) == "Dialogue script validation: ok"


def test_validate_dialogue_script_allows_technical_draft_tokens_term() -> None:
    result = validate_dialogue_script(
        """
mark: Сегодня разбираем ускорение генерации текста.
nika: А если по-человечески?
gleb: Быстрее не всегда значит проще в эксплуатации.
artem: Модель даёт черновики токенов, а основная модель проверяет их перед выдачей.
""",
    )

    assert result.has_errors is False
    assert result.has_blocking_issues is False


def test_validate_dialogue_script_blocks_non_dialogue_text() -> None:
    result = validate_dialogue_script(
        """
mark: Добрый день, сегодня девятое мая, и вы слушаете НикКаст.
Добрый день, сегодня девятое мая, и вы слушаете НикКаст.
nika: В выпуске короткие темы.
gleb: Я видел похожие истории.
artem: Практический риск здесь в интеграции.
""",
    )

    assert result.has_blocking_issues is True
    assert any(issue.code == "non_dialogue_text" for issue in result.issues)


def test_repair_dialogue_script_text_keeps_short_human_goodbye() -> None:
    script_text = """
mark: Риск не в анонсе, а в зависимости команды от внешнего сервиса.
nika: До встречи!
gleb: Я видел похожие истории.
artem: Команде нужен план отката и проверка доступа.
"""

    repaired = repair_dialogue_script_text(script_text)
    result = validate_dialogue_script(repaired, require_all_characters=False)

    assert "До встречи" in repaired
    assert result.has_blocking_issues is False


@pytest.mark.parametrize("prefix", ["**mark:**", "**mark**:", "__mark:__", "*Марк:*", "`mark`:"])
def test_repair_removes_only_known_speaker_formatting(prefix):
    wording = " C++ не заменяет C#; **важная оговорка** остаётся."
    repaired = repair_dialogue_script_text(prefix + wording)
    assert repaired.split(":", 1)[1] == wording
    assert not validate_dialogue_script(repaired).has_errors


def test_repair_does_not_hide_unknown_speakers_or_non_dialogue_headers():
    source = "**unknown:** Текст.\n# Служебный заголовок"
    assert repair_dialogue_script_text(source) == source
    assert validate_dialogue_script(source).has_errors


def test_inactive_known_speaker_rejected_only_for_new_generation():
    script = "mark: Привет.\ngleb: Обсудим новость."
    assert not validate_dialogue_script(script).has_errors
    result = validate_dialogue_script(script, allowed_speakers={"mark", "nika"})
    assert result.has_errors
    assert any(issue.code == "inactive_speaker" for issue in result.issues)
