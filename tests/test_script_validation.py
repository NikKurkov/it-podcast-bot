from app.podcast.script_validation import (
    format_validation_report,
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


def test_validate_dialogue_script_warns_when_character_is_missing() -> None:
    result = validate_dialogue_script(
        """
mark: Один.
gleb: Два.
nika: Три.
""",
    )

    assert result.has_errors is False
    assert result.has_blocking_issues is False
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


def test_validate_dialogue_script_errors_on_meta_phrase() -> None:
    result = validate_dialogue_script(
        """
mark: На этом всё, в следующий раз мы будем готовы к полноценному сценарию.
gleb: Я видел похожие истории.
nika: А если по-человечески?
artem: Здесь важно проверить контроль доступа.
""",
    )

    assert result.has_errors is True
    assert result.has_blocking_issues is True
    assert any("meta phrase" in issue.message for issue in result.issues)


def test_validate_dialogue_script_errors_on_stock_character_phrase() -> None:
    result = validate_dialogue_script(
        """
mark: Давайте восстановим цепочку событий.
gleb: Я видел похожие истории.
nika: А если по-человечески?
artem: Здесь важно проверить контроль доступа.
""",
    )

    assert result.has_errors is True
    assert result.has_blocking_issues is True
    assert any("stock character phrase" in issue.message for issue in result.issues)


def test_validate_dialogue_script_errors_on_copied_prompt_example_phrase() -> None:
    result = validate_dialogue_script(
        """
mark: Сегодня смотрим на практический риск.
gleb: Если обещают магию, сначала ищем место, где она будет ломаться.
nika: А если по-человечески?
artem: Здесь важно проверить контроль доступа.
""",
    )

    assert result.has_errors is True
    assert result.has_blocking_issues is True
    assert any("stock character phrase" in issue.message for issue in result.issues)


def test_validate_dialogue_script_errors_on_repeated_overused_phrase() -> None:
    result = validate_dialogue_script(
        """
mark: Сегодня смотрим на практический риск.
gleb: Звучит отлично. Осталось понять, кто это будет поддерживать.
nika: А если по-человечески?
artem: Практический риск здесь в интеграции.
gleb: Звучит отлично. Осталось понять, кто это будет поддерживать.
""",
    )

    assert result.has_errors is True
    assert result.has_blocking_issues is True
    assert any("is repeated" in issue.message for issue in result.issues)


def test_validate_dialogue_script_errors_on_unexpected_translation_block() -> None:
    result = validate_dialogue_script(
        """
mark: Сегодня смотрим на практический риск.
nika: А если по-человечески?
gleb: Я видел похожие истории.
artem: 这里出现了中文翻译块。
""",
    )

    assert result.has_errors is True
    assert result.has_blocking_issues is True
    assert any(issue.code == "unexpected_language" for issue in result.issues)
