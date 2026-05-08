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


def test_validate_dialogue_script_warns_on_generic_filler() -> None:
    result = validate_dialogue_script(
        """
mark: Сегодня смотрим на практический риск. Что же нас ждёт?
nika: А если по-человечески?
gleb: Я видел похожие истории.
artem: Здесь важно проверить контроль доступа.
""",
    )

    assert result.has_errors is False
    assert result.has_blocking_issues is True
    assert result.has_quality_retry_issues is True
    assert any(issue.code == "generic_filler" for issue in result.issues)


def test_validate_dialogue_script_warns_on_broad_intro_filler() -> None:
    result = validate_dialogue_script(
        """
mark: Сегодня мы поговорим о новых бенчмарках.
nika: Давайте разберём, как это влияет на команды.
gleb: Я видел похожие истории.
artem: Здесь важно проверить контроль доступа.
""",
    )

    assert result.has_errors is False
    assert result.has_blocking_issues is True
    assert result.has_quality_retry_issues is True
    assert len([issue for issue in result.issues if issue.code == "generic_filler"]) >= 2


def test_repair_dialogue_script_text_removes_meta_lines() -> None:
    script_text = """
mark: Сегодня смотрим на практический риск.
nika: А если по-человечески?
gleb: Я видел похожие истории.
artem: Здесь важно проверить контроль доступа.
mark: В следующем этапе мы превратим этот черновик в полноценный сценарий.
nika: Спасибо за внимание.
"""

    repaired = repair_dialogue_script_text(script_text)
    result = validate_dialogue_script(repaired)

    assert "черновик" not in repaired
    assert "Спасибо за внимание" in repaired
    assert result.has_blocking_issues is False


def test_repair_dialogue_script_text_removes_generic_filler_sentence() -> None:
    script_text = """
mark: Риск не в анонсе, а в зависимости команды от внешнего сервиса.
nika: А если по-человечески?
gleb: Я видел похожие истории.
artem: Команде нужен план отката и проверка доступа. Будем следить за развитием событий.
"""

    repaired = repair_dialogue_script_text(script_text)
    result = validate_dialogue_script(repaired)

    assert "Будем следить" not in repaired
    assert "план отката" in repaired
    assert result.has_blocking_issues is False


def test_repair_dialogue_script_text_removes_generic_filler_only_line() -> None:
    script_text = """
mark: Риск не в анонсе, а в зависимости команды от внешнего сервиса.
nika: До встречи!
gleb: Я видел похожие истории.
artem: Команде нужен план отката и проверка доступа.
"""

    repaired = repair_dialogue_script_text(script_text)
    result = validate_dialogue_script(repaired)

    assert "До встречи" not in repaired
    assert result.has_blocking_issues is False
