from app.podcast.script_quality import (
    build_script_quality_report,
    ensure_opening_and_rundown,
    postprocess_dialogue_script,
    quality_gate_allows_tts,
)


def test_postprocess_dialogue_script_repairs_and_reports_changes() -> None:
    result = postprocess_dialogue_script(
        """
mark: Сегодня мы поговорим о GitHub и доступности репозиториев.
nika: Сегодня в выпуске: GitHub, Claude и инфраструктура.
gleb: Да, но это уже было. Командам стоит проверить запасной доступ.
artem: Командам стоит зафиксировать план отката.
""",
    )

    assert "Сегодня мы поговорим" not in result.script_text
    assert "Командам стоит" not in result.script_text
    assert result.report["postprocess"]["changed"] is True
    assert result.report["lines_count"] == 4


def test_build_script_quality_report_detects_opening_rundown_and_transition() -> None:
    report = build_script_quality_report(
        """
mark: Добрый день, сегодня 09 мая, и вы слушаете НикКаст с обзором главных новостей в мире айти. Проверяем риски недели.
nika: Сегодня в выпуске: GitHub, Claude и инфраструктура.
gleb: А вот дальше история про доступность репозиториев.
artem: Проверьте зеркала и план отката.
""",
    )

    assert report["opening_present"] is True
    assert report["rundown_present"] is True
    assert report["transition_lines"] >= 1


def test_postprocess_dialogue_script_adds_outro_for_long_episode() -> None:
    result = postprocess_dialogue_script(
        """
mark: Добрый день, сегодня 09 мая, и вы слушаете НикКаст с обзором главных новостей в мире айти. Проверяем риски недели.
nika: В выпуске: GitHub, Claude и инфраструктура.
gleb: Ника, выбирай первую тему.
artem: GitHub требует резервного плана доступа.
mark: А вот дальше история про безопасность аккаунтов.
nika: Подожди, здесь важен контроль прав.
gleb: Красивые кнопки не заменяют аудит.
artem: Проверьте роли и токены доступа.
mark: Переключаемся на инфраструктуру.
nika: Марк, здесь снова вопрос к процессам.
gleb: Без мониторинга всё узнают из чата.
artem: Зафиксируйте алерты и план отката.
""",
    )
    report = build_script_quality_report(result.script_text)

    assert "С вами были Марк, Ника, Глеб и Артём" in result.script_text
    assert report["outro_present"] is True


def test_build_script_quality_report_tracks_liveness_markers() -> None:
    report = build_script_quality_report(
        """
mark: Добрый день, сегодня 09 мая, и вы слушаете НикКаст с обзором главных новостей в мире айти. Проверяем риски недели.
nika: В выпуске: GitHub, Claude и инфраструктура.
gleb: Ника, выбирай следующую тему, только без рекламного блеска.
nika: Подожди, Глеб, здесь как раз важна практическая часть.
artem: Марк, технический риск в том, что команда теряет воспроизводимость сборки.
mark: Артём, зафиксируем вывод: проверьте зеркала и план отката.
""",
    )

    assert report["direct_address_lines"] >= 3
    assert report["interruption_lines"] >= 1


def test_ensure_opening_and_rundown_adds_missing_intro() -> None:
    script = """
gleb: GitHub снова проверяет терпение команд.
artem: Проверьте зеркала и план отката.
"""

    fixed = ensure_opening_and_rundown(
        script,
        topic_summaries=["GitHub API outage affected production releases."],
    )
    report = build_script_quality_report(fixed)

    assert "Добрый день" in fixed
    assert "НикКаст" in fixed
    assert "В выпуске:" in fixed
    assert report["opening_present"] is True
    assert report["rundown_present"] is True


def test_quality_gate_blocks_missing_opening() -> None:
    report = build_script_quality_report(
        """
mark: GitHub снова проверяет терпение команд.
nika: В выпуске: GitHub и инфраструктура.
gleb: А вот дальше история про доступность.
artem: Проверьте зеркала и план отката.
""",
    )

    allowed, blocking = quality_gate_allows_tts(report)

    assert allowed is False
    assert "opening_missing" in blocking
