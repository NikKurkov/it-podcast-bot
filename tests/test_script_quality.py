from app.podcast.script_quality import (
    build_script_quality_report,
    postprocess_dialogue_script,
    quality_gate_allows_tts,
)


def test_quality_report_does_not_require_canned_framing():
    report = build_script_quality_report(
        "nika: А что изменилось для пользователей?\nartem: Пока неизвестно."
    )
    assert not any("opening" in warning or "rundown" in warning for warning in report["warnings"])
    assert report["speaker_counts"]["nika"] == 1


def test_build_script_quality_report_includes_text_lint() -> None:
    report = build_script_quality_report(
        """
mark: Здесь важно проверить доступы.
nika: Здесь важно проверить данные.
gleb: Здесь важно проверить сборку.
artem: Практический вывод простой: проверьте логи.
mark: Практический вывод простой: проверьте лимиты.
""",
    )

    lint = report["text_lint"]

    assert lint["repeated_line_starts"]["здесь важно проверить"] == 3
    assert "text_lint:repeated_line_start:здесь важно проверить" in report["warnings"]


def test_quality_gate_allows_different_opening_styles() -> None:
    report = build_script_quality_report(
        """
mark: GitHub снова проверяет терпение команд.
nika: В выпуске: GitHub и инфраструктура.
gleb: А вот дальше история про доступность.
artem: Проверьте зеркала и план отката.
""",
    )

    allowed, blocking = quality_gate_allows_tts(report)

    assert allowed is True
    assert blocking == []


def test_postprocess_preserves_meaningful_what_does_it_mean_question():

    result = postprocess_dialogue_script("nika: Что значит обратная совместимость API?")
    assert "Что значит обратная совместимость API?" in result.script_text


def test_quality_report_estimates_spoken_duration_without_speaker_names():
    from app.podcast.script_quality import build_script_quality_report

    report = build_script_quality_report("mark: " + " ".join(["совместимость"] * 135))
    assert report["word_count"] == 135
    assert 60 <= report["estimated_duration_seconds"] <= 100
    assert report["duration_status"] == "short"
    assert "duration_short" in report["warnings"]


def test_quality_report_keeps_unknown_speaker_validation():
    from app.podcast.script_quality import build_script_quality_report, quality_gate_allows_tts

    script = "\n".join(
        [
            "mark: Добрый день, вы слушаете НикКаст с обзором новостей.",
            "nika: В выпуске новые инструменты и API.",
            "gleb: Условия доступа пока прежние.",
            "artem: Версии клиента совместимы.",
            "mark: Сервис поддерживает прежний протокол.",
            "nika: Старый клиент продолжит работать.",
            "gleb: Это полезная деталь для миграции.",
            "artem: До новых встреч.",
            "unknown: Эту строку нельзя молча озвучивать.",
        ]
    )
    report = build_script_quality_report(script)
    allowed, blocking = quality_gate_allows_tts(report)
    assert not allowed
    assert "validation_issues" in blocking


def test_tts_gate_allows_sparse_conversation_without_artificial_transitions():
    report = {
        "opening_present": True,
        "rundown_present": True,
        "outro_present": True,
        "lines_count": 18,
        "transition_lines": 0,
        "speaker_counts": {"mark": 9, "nika": 9, "gleb": 0, "artem": 0},
        "validation_issues": [{"severity": "warning", "code": "speaker_streak"}],
    }
    assert quality_gate_allows_tts(report) == (True, [])
