from app.podcast.script_quality import build_script_quality_report, postprocess_dialogue_script


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
