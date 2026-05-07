from app.podcast.script_validation import (
    format_validation_report,
    validate_dialogue_script,
)


def test_validate_dialogue_script_accepts_final_characters() -> None:
    result = validate_dialogue_script(
        """
mark: Давайте восстановим цепочку событий.
gleb: Я такое уже видел.
nika: А если по-человечески?
artem: В продакшене это упирается в контроль доступа.
""",
    )

    assert result.has_errors is False
    assert result.lines_count == 4
    assert result.speakers == ["mark", "gleb", "nika", "artem"]


def test_validate_dialogue_script_reports_legacy_character() -> None:
    result = validate_dialogue_script("boris: Старый формат.")

    assert result.has_errors is True
    assert any("boris" in issue.message for issue in result.issues)


def test_validate_dialogue_script_warns_when_character_is_missing() -> None:
    result = validate_dialogue_script(
        """
mark: Один.
gleb: Два.
nika: Три.
""",
    )

    assert result.has_errors is False
    assert any("Missing: artem" in issue.message for issue in result.issues)


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
