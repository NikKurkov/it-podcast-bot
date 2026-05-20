from app.podcast.script_quality import (
    build_script_quality_report,
    ensure_opening_and_rundown,
    postprocess_dialogue_script,
    quality_gate_allows_tts,
)
from app.config.settings import settings


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


def test_postprocess_dialogue_script_normalizes_capitalization_and_duplicate_opening() -> None:
    result = postprocess_dialogue_script(
        """
mark: Добрый день, сегодня девятое мая, и вы слушаете НикКаст с обзором главных новостей в мире айти.
mark: Добрый день, сегодня девятое мая, и вы слушаете НикКаст с обзором главных новостей в мире айти.
artem: это важно для команд. практическое действие: проверить доступы.
""",
    )

    assert result.script_text.count("Добрый день") == 1
    assert "artem: Это важно для команд. Практическое действие" in result.script_text


def test_postprocess_dialogue_script_normalizes_ellipsized_rundown() -> None:
    result = postprocess_dialogue_script(
        """
mark: Добрый день, сегодня девятое мая, и вы слушаете НикКаст с обзором главных новостей в мире айти.
nika: В выпуске: Discord массово сбоит по всему миру — сервис не запускается. За п...; РКН добрался до GitHub? Сервис отслеживания OONI зафиксировал снижение....
gleb: Я видел похожие истории.
artem: Проверьте доступы и план отката.
""",
    )

    assert "Discord массово сбоит по всему миру; РКН добрался до GitHub." in result.script_text
    assert "..." not in result.script_text


def test_postprocess_dialogue_script_cleans_truncated_rundown_fragments() -> None:
    result = postprocess_dialogue_script(
        """
mark: Добрый день, сегодня пятнадцатое мая, и вы слушаете НикКаст с обзором главных новостей в мире айти.
nika: В выпуске: Новый Li Auto L9 Livis официально появится в России во второй половине года Продажи экс; Crocs и Red Bull выпустят коллекцию сабо в виде болидов Формулы-1 Старт продаж заплан.
gleb: Я видел похожие истории.
artem: Проверьте доступы и план отката.
""",
    )

    assert "Продажи экс" not in result.script_text
    assert "заплан" not in result.script_text
    assert "..." not in result.script_text


def test_postprocess_dialogue_script_replaces_weak_rundown_titles() -> None:
    result = postprocess_dialogue_script(
        """
mark: Добрый день, сегодня девятнадцатое мая, и вы слушаете НикКаст с обзором главных новостей в мире айти.
nika: В выпуске: Finally... 1 кГц LG готовит первый Full HD-монитор; Факт дня: этим летом россиянам доступно меньше прямых рейсов; Krea 2, которая создаёт.
gleb: Я видел похожие истории.
artem: Проверьте доступы и план отката.
""",
    )

    assert "Finally" not in result.script_text
    assert "Факт дня;" not in result.script_text
    assert "1 кГц LG готовит первый Full HD-монитор" in result.script_text
    assert "этим летом россиянам доступно меньше прямых рейсов" in result.script_text
    assert "которая создаёт" not in result.script_text


def test_postprocess_dialogue_script_removes_standalone_weak_transition_titles() -> None:
    result = postprocess_dialogue_script(
        """
nika: А вот следующая тема: Finally.
gleb: Я бы перевела это проще: 1 кГц LG готовит к выпуску первый Full HD-монитор с поддержкой 1000 Гц.
artem: Переключаемся на практический риск: Факт дня: этим летом россиянам доступно меньше прямых рейсов.
""",
    )

    assert "А вот следующая тема: Finally" not in result.script_text
    assert "Переключаемся на практический риск: этим летом" in result.script_text
    assert "Full HD-монитор" in result.script_text


def test_postprocess_dialogue_script_varies_mechanical_phrases_and_self_addresses() -> None:
    result = postprocess_dialogue_script(
        """
mark: Ника, а по-человечески, что это значит для обычных пользователей?
nika: Ника, а по-человечески, это просто риск для сервиса.
gleb: Глеб, а по-человечески, запасной план опять забыли.
artem: Артем, практический вывод для разработчиков и пользователей: проверить доступы.
""",
    )

    assert result.script_text.count("а по-человечески") <= 1
    assert "nika: Ника," not in result.script_text
    assert "gleb: Глеб," not in result.script_text
    assert "artem: Артем," not in result.script_text
    assert "практический вывод для разработчиков и пользователей" not in result.script_text


def test_postprocess_dialogue_script_varies_repeated_stock_sentences() -> None:
    result = postprocess_dialogue_script(
        """
mark: Тут не хайп важен, а то, насколько команда понимает, где у неё точка отказа.
nika: Тут не хайп важен, а то, насколько команда понимает, где у неё точка отказа.
gleb: Практический смысл простой: меньше догадок, больше проверяемых фактов и наблюдаемости.
artem: Практический смысл простой: меньше догадок, больше проверяемых фактов и наблюдаемости.
""",
    )

    assert result.script_text.count("Тут не хайп важен") <= 1
    assert result.script_text.count("Практический смысл простой") <= 1
    assert "точка отказа" in result.script_text


def test_postprocess_dialogue_script_smooths_repeated_checking_phrase() -> None:
    result = postprocess_dialogue_script(
        """
mark: Анонс звучит бодро, но его еще надо проверять: проверять придётся реальные ограничения.
nika: Витрина красивая, а ограничения всё равно придется смотреть руками: проверять придётся реальные ограничения.
gleb: Тут не хайп важен, а то, насколько команда понимает, где у неё точка отказа.
artem: Практический смысл простой: меньше догадок, больше проверяемых фактов и наблюдаемости.
""",
    )

    assert "проверять: проверять" not in result.script_text
    assert "смотреть руками: проверять" not in result.script_text


def test_postprocess_dialogue_script_thins_excess_direct_addresses() -> None:
    result = postprocess_dialogue_script(
        """
mark: Ника, открываем тему про доступность GitHub.
nika: Марк, я бы сразу спросила про запасной доступ.
gleb: Ника, запасной доступ вспоминают обычно после пожара.
artem: Глеб, здесь важна воспроизводимость сборки.
mark: Артём, зафиксируем риск для релизов.
nika: Подожди, Глеб, но это же ломает обычный рабочий день.
gleb: Марк, рабочий день ломает отсутствие плана.
artem: Ника, команде нужен простой чеклист.
""",
    )

    report = build_script_quality_report(result.script_text)

    assert report["direct_address_lines"] <= 2
    assert "Подожди, но это же ломает" in result.script_text
    assert "Глеб, здесь важна" not in result.script_text


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

    assert "На этом всё" in result.script_text
    assert "С вами были Марк, Ника, Глеб и Артём" in result.script_text
    assert report["outro_present"] is True
    assert report["outro_end_marker_present"] is True


def test_postprocess_dialogue_script_inserts_outro_end_marker_before_goodbye() -> None:
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
artem: Проверьте алерты и план отката.
nika: Хорошего вам дня и спокойных релизов.
""",
    )

    assert "На этом всё, это были главные новости на сегодня." in result.script_text
    assert result.script_text.index("На этом всё") < result.script_text.index("Хорошего вам дня")


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

    assert report["direct_address_lines"] >= 2
    assert report["interruption_lines"] >= 1


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

    assert lint["word_counts"]["важно"] >= 3
    assert lint["construct_counts"]["здесь_важно"] == 3
    assert lint["repeated_line_starts"]["здесь важно проверить"] == 3
    assert "text_lint:repeated_construct:здесь_важно" in report["warnings"]
    assert "text_lint:repeated_line_start:здесь важно проверить" in report["warnings"]


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
    assert settings.podcast_title in fixed
    assert "Разбираем, где в этих историях технический риск, а где просто шум" not in fixed
    assert "В выпуске:" in fixed
    assert report["opening_present"] is True
    assert report["rundown_present"] is True


def test_postprocess_dialogue_script_fixes_first_person_gender_agreement() -> None:
    result = postprocess_dialogue_script(
        """
gleb: Я бы перевела это проще: GitHub опять проверяет рабочий процесс.
artem: Я бы спросила про конкретный механизм отказа.
nika: Я бы перевел это на человеческий язык.
""",
    )

    assert "gleb: Я бы перевёл это проще" in result.script_text
    assert "artem: Я бы спросил" in result.script_text
    assert "nika: Я бы перевела" in result.script_text


def test_postprocess_dialogue_script_tightens_editorial_labels() -> None:
    result = postprocess_dialogue_script(
        """
artem: Здесь важно проверить токены доступа до релиза.
mark: Для команды вывод простой: держите факты рядом с планом действий.
nika: Практический шаг простой: сравните обещание с фактическим ограничением.
""",
    )

    assert "artem: Проверьте токены доступа до релиза." in result.script_text
    assert "mark: Для команды: держите факты рядом" in result.script_text
    assert "Практический шаг простой" not in result.script_text


def test_ensure_opening_and_rundown_uses_short_topic_titles() -> None:
    fixed = ensure_opening_and_rundown(
        "gleb: GitHub снова проверяет терпение команд.",
        topic_summaries=[
            "Discord массово сбоит по всему миру — сервис не запускается ни на одной платформе.",
            "РКН добрался до GitHub? Сервис отслеживания интернет-цензуры OONI зафиксировал снижение.",
        ],
    )

    assert "Discord массово сбоит по всему миру; РКН добрался до GitHub." in fixed
    assert "..." not in fixed


def test_ensure_opening_and_rundown_compacts_long_topic_titles() -> None:
    fixed = ensure_opening_and_rundown(
        "gleb: GitHub снова проверяет терпение команд.",
        topic_summaries=[
            "OpenAI представила новые voice-модели для разработчиков с дополнительными режимами генерации и длинным описанием возможностей.",
            "Discord массово сбоит по всему миру, сервис не запускается ни на одной платформе у пользователей.",
            "CVE-2026-1234 в Kubernetes позволяет обойти ограничение доступа при редкой конфигурации кластера.",
        ],
    )

    assert "OpenAI представила новые voice-модели" in fixed
    assert "Discord массово сбоит по всему миру" in fixed
    assert "CVE-2026-1234" in fixed
    assert "длинным описанием возможностей" not in fixed


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
