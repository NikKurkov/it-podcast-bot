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
    assert result.has_blocking_issues is True
    assert any("Missing: artem" in issue.message for issue in result.issues)


def test_validate_dialogue_script_blocks_next_episode_outro() -> None:
    result = validate_dialogue_script(
        """
mark: Риск не в анонсе, а в зависимости команды от внешнего сервиса.
gleb: Я видел похожие истории.
nika: Практический вопрос в том, где запасной путь.
artem: Команде нужен план отката и проверка доступа.
mark: В следующем выпуске мы продолжим следить за обновлениями.
""",
    )

    assert result.has_blocking_issues is True
    assert any(issue.code == "generic_filler" for issue in result.issues)


def test_validate_dialogue_script_blocks_service_leak() -> None:
    result = validate_dialogue_script(
        """
mark: Риск не в анонсе, а в зависимости команды от внешнего сервиса.
nika: Auto-selected by final run score=13.58, поэтому эта тема важна.
gleb: Я видел похожие истории.
artem: Команде нужен план отката и проверка доступа.
""",
    )

    assert result.has_errors is True
    assert result.has_blocking_issues is True
    assert any(issue.code == "service_leak" for issue in result.issues)


def test_validate_dialogue_script_blocks_bad_opening_speaker() -> None:
    result = validate_dialogue_script(
        """
nika: Практический вопрос в том, где запасной путь.
mark: Риск не в анонсе, а в зависимости команды от внешнего сервиса.
gleb: Я видел похожие истории.
artem: Команде нужен план отката и проверка доступа.
""",
    )

    assert result.has_blocking_issues is True
    assert any(issue.code == "bad_opening_speaker" for issue in result.issues)


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
    assert any(issue.code == "markdown_separator" for issue in result.issues)


def test_validate_dialogue_script_blocks_underused_character() -> None:
    result = validate_dialogue_script(
        """
mark: Один.
mark: Два.
mark: Три.
gleb: Три.
nika: Четыре.
nika: Пять.
artem: Шесть.
artem: Семь.
artem: Восемь.
""",
    )

    assert result.has_errors is False
    assert result.has_blocking_issues is True
    assert any(issue.code == "underused_character" for issue in result.issues)


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


def test_validate_dialogue_script_blocks_repeated_robotic_questions() -> None:
    result = validate_dialogue_script(
        """
mark: Сегодня смотрим на практический риск.
nika: А по-человечески, где здесь боль команды?
gleb: Я видел похожие истории.
artem: Практический риск здесь в интеграции.
nika: А по-человечески, кто будет это поддерживать?
""",
    )

    assert result.has_errors is True
    assert result.has_blocking_issues is True
    assert any(issue.code == "repeated_phrase" for issue in result.issues)


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


def test_validate_dialogue_script_blocks_repetitive_transition_filler() -> None:
    result = validate_dialogue_script(
        """
mark: Давайте перейдём к следующей новости.
nika: Как это поможет обычному разработчику?
gleb: Я видел похожие истории.
artem: Здесь важен план отката.
""",
    )

    assert result.has_blocking_issues is True
    assert len([issue for issue in result.issues if issue.code == "generic_filler"]) >= 2


def test_validate_dialogue_script_blocks_generic_developer_question() -> None:
    result = validate_dialogue_script(
        """
mark: Риск здесь в цепочке поставки пакета.
nika: И как это влияет на обычного разработчика?
gleb: Я видел похожие истории.
artem: Здесь важен план отката.
""",
    )

    assert result.has_blocking_issues is True
    assert any(issue.code == "generic_filler" for issue in result.issues)


def test_validate_dialogue_script_blocks_generic_closing() -> None:
    result = validate_dialogue_script(
        """
mark: Риск здесь в цепочке поставки пакета.
nika: Практический вопрос в том, кто проверяет обновления.
gleb: Я видел похожие истории.
artem: Здесь важен план отката.
mark: На этом наш выпуск подходит к концу.
""",
    )

    assert result.has_blocking_issues is True
    assert any(issue.code == "generic_filler" for issue in result.issues)


def test_validate_dialogue_script_blocks_bland_acknowledgement_lines() -> None:
    result = validate_dialogue_script(
        """
mark: Риск здесь в цепочке поставки пакета.
nika: Интересно, как это может повлиять на наши проекты?
gleb: Абсолютно верно. Я видел похожие истории.
artem: Здесь важен план отката.
""",
    )

    assert result.has_blocking_issues is True
    assert len([issue for issue in result.issues if issue.code == "generic_filler"]) >= 2


def test_validate_dialogue_script_blocks_repeated_team_should_phrase() -> None:
    result = validate_dialogue_script(
        """
mark: Риск здесь в цепочке поставки пакета.
nika: Практический вопрос в том, кто проверяет обновления.
gleb: Командам стоит не верить красивым словам без плана отката.
artem: Командам стоит вынести проверку доступа в релизный чеклист.
""",
    )

    assert result.has_errors is True
    assert result.has_blocking_issues is True
    assert any(issue.code == "repeated_phrase" for issue in result.issues)


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
    result = validate_dialogue_script(repaired, require_all_characters=False)

    assert "черновик" not in repaired
    assert "Спасибо за внимание" not in repaired
    assert result.has_blocking_issues is False


def test_repair_dialogue_script_text_removes_generic_filler_sentence() -> None:
    script_text = """
mark: Риск не в анонсе, а в зависимости команды от внешнего сервиса.
nika: А если по-человечески?
gleb: Я видел похожие истории.
artem: Команде нужен план отката и проверка доступа. Будем следить за развитием событий.
"""

    repaired = repair_dialogue_script_text(script_text)
    result = validate_dialogue_script(repaired, require_all_characters=False)

    assert "Будем следить" not in repaired
    assert "план отката" in repaired
    assert result.has_blocking_issues is False


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


def test_repair_dialogue_script_text_removes_generic_outro_line() -> None:
    script_text = """
mark: Риск не в анонсе, а в зависимости команды от внешнего сервиса.
nika: До следующего выпуска!
gleb: Я видел похожие истории.
artem: Команде нужен план отката и проверка доступа.
"""

    repaired = repair_dialogue_script_text(script_text)
    result = validate_dialogue_script(repaired, require_all_characters=False)

    assert "До следующего выпуска" not in repaired
    assert result.has_blocking_issues is False


def test_repair_dialogue_script_text_removes_thanks_outro_line() -> None:
    script_text = """
mark: Риск не в анонсе, а в зависимости команды от внешнего сервиса.
nika: Практический вопрос в том, где запасной путь.
gleb: Я видел похожие истории.
artem: Команде нужен план отката и проверка доступа.
mark: Спасибо за внимание!
"""

    repaired = repair_dialogue_script_text(script_text)

    assert "Спасибо за внимание" not in repaired


def test_repair_dialogue_script_text_rewrites_repeated_team_should_phrase() -> None:
    script_text = """
mark: Сегодня мы поговорим о вайбкодинге и его последствиях.
nika: Интересно, как это влияет на обычного разработчика? Может, он просто перестанет учиться?
gleb: Да, но это уже было. Вайбкодинг — это новый тренд на старую идею автоматизации.
artem: Командам стоит проверить качество генерируемого кода перед внедрением.
mark: Давайте перейдем к следующей новости о снижении доступности GitHub в России.
nika: А по-человечески? Это как если бы кто-то заблокировал доступ к репозиториям?
gleb: И это уже было не раз.
artem: Командам стоит заложить мониторинг доступности в систему оперативного управления.
mark: На этом наш выпуск подходит к концу. Спасибо за внимание, проверьте состояние сервисов.
"""

    repaired = repair_dialogue_script_text(script_text)
    result = validate_dialogue_script(repaired)

    assert "Командам стоит" not in repaired
    assert "Давайте перейдем" not in repaired
    assert "Сегодня мы поговорим" not in repaired
    assert "Спасибо за внимание" not in repaired
    assert result.has_blocking_issues is False


def test_repair_dialogue_script_text_removes_markdown_separator() -> None:
    script_text = """
mark: Риск не в анонсе, а в зависимости команды от внешнего сервиса.
---
nika: Практический вопрос в том, где запасной путь.
gleb: Я видел похожие истории.
artem: Команде нужен план отката и проверка доступа.
"""

    repaired = repair_dialogue_script_text(script_text)

    assert "---" not in repaired
