from app.podcast.script_quality import build_script_quality_report, postprocess_dialogue_script


def test_golden_script_removes_typical_mechanical_phrases() -> None:
    result = postprocess_dialogue_script(
        """
mark: Сегодня мы поговорим о практическом риске GitHub.
nika: Ника, а по-человечески, что это значит для обычных пользователей?
gleb: Глеб, а по-человечески, запасной план опять забыли.
artem: Командам стоит проверить доступы.
mark: Давайте перейдем к следующей новости о Discord.
nika: Интересно, как это влияет на обычного разработчика?
gleb: Да, но это уже было. Командам стоит следить за такими новостями.
artem: Здесь важно проверить контроль доступа.
""",
    )

    normalized = result.script_text.casefold().replace("ё", "е")

    assert "сегодня мы поговорим" not in normalized
    assert normalized.count("а по-человечески") <= 1
    assert "командам стоит" not in normalized
    assert "давайте перейдем" not in normalized
    assert "интересно, как это влияет" not in normalized


def test_golden_script_flags_stiff_report_style() -> None:
    report = build_script_quality_report(
        """
mark: Здесь важно проверить доступы.
nika: Здесь важно проверить данные.
gleb: Здесь важно проверить сборку.
artem: Здесь важно проверить релиз.
mark: Практический вывод простой: проверьте логи.
nika: Практический вывод простой: проверьте лимиты.
""",
    )

    assert "text_lint:overused_word:важно" in report["warnings"]
    assert "text_lint:repeated_construct:здесь_важно" in report["warnings"]
    assert "text_lint:repeated_line_start:здесь важно проверить" in report["warnings"]


def test_golden_script_keeps_consumer_signal_short_without_engineering_advice() -> None:
    result = postprocess_dialogue_script(
        """
mark: Короткий сигнал из потребительской ленты: Crocs и Red Bull выпустят коллекцию сабо в виде болидов Формулы-1.
nika: Из фактов здесь только это: старт продаж запланирован на 21 мая.
gleb: В инженерную проблему это не превращаем: данных про платформы, API или эксплуатацию в новости нет.
artem: Поэтому оставляем как фон рынка, без чеклиста для разработки.
""",
    )

    normalized = result.script_text.casefold().replace("ё", "е")

    assert "резервный план" not in normalized
    assert "проверьте доступ" not in normalized
    assert "без чеклиста для разработки" in normalized
