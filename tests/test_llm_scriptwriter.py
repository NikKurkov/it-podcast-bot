from types import SimpleNamespace

from app.llm import scriptwriter


class FakeCompletions:
    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="Готовый сценарий"),
                ),
            ],
        )


class FakeChat:
    def __init__(self) -> None:
        self.completions = FakeCompletions()


class FakeClient:
    def __init__(self) -> None:
        self.chat = FakeChat()


def test_rewrite_script_draft_uses_chat_completions(monkeypatch) -> None:
    fake_client = FakeClient()
    monkeypatch.setattr(scriptwriter, "create_llm_client", lambda: fake_client)

    result = scriptwriter.rewrite_script_draft("Черновик", model="local-model", system_prompt="System")

    assert result == "Готовый сценарий"
    assert fake_client.chat.completions.kwargs["model"] == "local-model"
    assert fake_client.chat.completions.kwargs["messages"][0]["content"] == "System"
    assert fake_client.chat.completions.kwargs["messages"][1]["content"] == "Черновик"


def test_rewrite_dialogue_script_draft_uses_dialogue_prompt(monkeypatch) -> None:
    fake_client = FakeClient()
    monkeypatch.setattr(scriptwriter, "create_llm_client", lambda: fake_client)

    result = scriptwriter.rewrite_dialogue_script_draft("Черновик", model="local-model")

    assert result == "Готовый сценарий"
    system_prompt = fake_client.chat.completions.kwargs["messages"][0]["content"]
    assert "mark" in system_prompt
    assert "gleb" in system_prompt
    assert "nika" in system_prompt
    assert "artem" in system_prompt
    assert "Марк" in system_prompt


def test_rewrite_validated_dialogue_script_draft_retries_invalid_output(monkeypatch) -> None:
    outputs = iter(
        [
            """
mark: Сегодня смотрим на риск.
nika: А если по-человечески?
gleb: Я видел похожие истории.
artem: 这里出现了中文翻译块。
""",
            """
mark: Сегодня смотрим на риск.
nika: А если по-человечески?
gleb: Я видел похожие истории.
artem: Здесь важно проверить доступы и план отката.
""",
        ],
    )
    calls = []

    def fake_rewrite(*args, **kwargs):
        calls.append(kwargs)
        return next(outputs)

    monkeypatch.setattr(scriptwriter, "rewrite_dialogue_script_draft", fake_rewrite)

    script_text, validation = scriptwriter.rewrite_validated_dialogue_script_draft(
        "Черновик",
        model="local-model",
        attempts=2,
    )

    assert validation.has_blocking_issues is False
    assert "Здесь важно проверить доступы" in script_text
    assert len(calls) == 2


def test_rewrite_validated_dialogue_script_draft_repairs_meta_outro(monkeypatch) -> None:
    def fake_rewrite(*args, **kwargs):
        return """
mark: Сегодня смотрим на практический риск.
nika: А если по-человечески?
gleb: Я видел похожие истории.
artem: Здесь важно проверить доступы и план отката.
mark: В следующем этапе мы превратим этот черновик в полноценный сценарий.
nika: Спасибо за внимание.
"""

    monkeypatch.setattr(scriptwriter, "rewrite_dialogue_script_draft", fake_rewrite)

    script_text, validation = scriptwriter.rewrite_validated_dialogue_script_draft(
        "Черновик",
        attempts=1,
    )

    assert validation.has_blocking_issues is False
    assert "черновик" not in script_text
    assert "Спасибо за внимание" not in script_text


def test_rewrite_validated_dialogue_script_draft_repairs_quality_warnings(monkeypatch) -> None:
    seen_drafts = []

    def fake_rewrite(draft_text, *args, **kwargs):
        seen_drafts.append(draft_text)
        return """
mark: Сегодня мы поговорим о практическом риске.
nika: А если по-человечески?
gleb: Я видел похожие истории.
artem: Здесь важно проверить доступы и план отката.
"""

    monkeypatch.setattr(scriptwriter, "rewrite_dialogue_script_draft", fake_rewrite)

    script_text, validation = scriptwriter.rewrite_validated_dialogue_script_draft(
        "Черновик",
        attempts=2,
    )

    assert validation.has_quality_retry_issues is False
    assert "Сегодня мы поговорим" not in script_text
    assert len(seen_drafts) == 1


def test_rewrite_validated_dialogue_script_draft_raises_after_attempts(monkeypatch) -> None:
    def fake_rewrite(*args, **kwargs):
        return """
mark: Сегодня смотрим на риск.
nika: А если по-человечески?
gleb: Я видел похожие истории.
artem: 这里出现了中文翻译块。
"""

    monkeypatch.setattr(scriptwriter, "rewrite_dialogue_script_draft", fake_rewrite)

    try:
        scriptwriter.rewrite_validated_dialogue_script_draft("Черновик", attempts=1)
    except RuntimeError as exc:
        assert "invalid dialogue script" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_rewrite_validated_dialogue_script_draft_raises_on_unrepairable_quality_issue(
    monkeypatch,
) -> None:
    def fake_rewrite(*args, **kwargs):
        return """
mark: Сегодня мы поговорим о риске.
nika: А если по-человечески?
gleb: Я видел похожие истории.
"""

    monkeypatch.setattr(scriptwriter, "rewrite_dialogue_script_draft", fake_rewrite)

    try:
        scriptwriter.rewrite_validated_dialogue_script_draft("Черновик", attempts=2)
    except RuntimeError as exc:
        assert "Missing: artem" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_rewrite_validated_dialogue_script_draft_allows_quality_fallback(monkeypatch) -> None:
    def fake_rewrite(*args, **kwargs):
        return """
mark: Добрый день, сегодня десятое мая, и вы слушаете НикКаст с обзором главных новостей в мире айти. Сегодня мы поговорим о сбоях сервисов.
nika: Интересно, как это влияет на обычного разработчика?
gleb: Командам стоит проверить резервный канал связи.
artem: Командам стоит зафиксировать порядок эскалации.
mark: На этом всё, это были главные новости на сегодня.
"""

    monkeypatch.setattr(scriptwriter, "rewrite_dialogue_script_draft", fake_rewrite)

    script_text, validation = scriptwriter.rewrite_validated_dialogue_script_draft(
        "Черновик",
        attempts=1,
        allow_quality_fallback=True,
    )

    assert validation.has_structural_blocking_issues is False
    assert "Командам стоит" not in script_text
    assert "проверка для команды" in script_text.casefold()


def test_rewrite_chunked_dialogue_script_draft_generates_by_news_blocks(monkeypatch) -> None:
    calls = []

    def fake_rewrite(prompt, *args, **kwargs):
        calls.append(prompt)
        return """
mark: Смотрим на конкретный факт.
nika: Здесь важно не потерять смысл новости.
gleb: Красивый анонс не отменяет проверки.
artem: Практический вывод — фиксируем ограничения.
"""

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", fake_rewrite)

    draft = """
# Test

### 1. @src #1
Fact lock:
- Main claim: Первый факт
- Allowed fact: Первый факт делает одну вещь

### 2. @src #2
Fact lock:
- Main claim: Второй факт
- Allowed fact: Второй факт делает другую вещь

### 3. @src #3
Fact lock:
- Main claim: Третий факт
- Allowed fact: Третий факт делает третью вещь
"""

    script_text, validation = scriptwriter.rewrite_chunked_dialogue_script_draft(
        draft,
        model="local-model",
        chunk_size=2,
    )

    assert len(calls) == 2
    assert validation.has_structural_blocking_issues is False
    assert "На этом всё" in script_text


def test_rewrite_chunked_dialogue_script_draft_uses_deterministic_chunk_fallback(
    monkeypatch,
) -> None:
    def fake_rewrite(*args, **kwargs):
        raise RuntimeError("local model timed out")

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", fake_rewrite)

    draft = """
### 1. @src #1
Fact lock:
- Main claim: GitHub снизил доступность
- Allowed fact: OONI зафиксировал снижение доступности GitHub в России
"""

    script_text, validation = scriptwriter.rewrite_chunked_dialogue_script_draft(
        draft,
        model="local-model",
        chunk_size=2,
    )

    assert validation.has_structural_blocking_issues is False
    assert "GitHub снизил доступность" in script_text
    assert "OONI зафиксировал" in script_text


def test_deterministic_chunk_fallback_does_not_invent_production_risk_for_consumer_topic(
    monkeypatch,
) -> None:
    def fake_rewrite(*args, **kwargs):
        raise RuntimeError("local model timed out")

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", fake_rewrite)

    draft = """
### 1. @src #1
Fact lock:
- Main claim: Crocs и Red Bull выпустят коллекцию сабо в виде болидов Формулы-1
- Allowed fact: Старт продаж запланирован на 21 мая
"""

    script_text, validation = scriptwriter.rewrite_chunked_dialogue_script_draft(
        draft,
        model="local-model",
        chunk_size=2,
    )

    assert validation.has_structural_blocking_issues is False
    consumer_scene = script_text.split("mark: На этом всё", 1)[0]

    assert "В инженерную проблему это не превращаем" in consumer_scene
    assert "без чеклиста для разработки" in consumer_scene
    assert "резервный план" not in consumer_scene
    assert "доступ" not in consumer_scene.casefold()


def test_deterministic_chunk_fallback_keeps_monitor_news_as_consumer_signal(
    monkeypatch,
) -> None:
    def fake_rewrite(*args, **kwargs):
        raise RuntimeError("local model timed out")

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", fake_rewrite)

    draft = """
### 1. @src #1
Fact lock:
- Main claim: Finally... 1 кГц LG готовит к выпуску первый Full HD-монитор с поддержкой 1000 Гц
- Allowed fact: Ранее такую частоту обновления показывали только прототипы
"""

    script_text, validation = scriptwriter.rewrite_chunked_dialogue_script_draft(
        draft,
        model="local-model",
        chunk_size=2,
    )

    assert validation.has_structural_blocking_issues is False
    consumer_scene = script_text.split("mark: На этом всё", 1)[0]

    assert "Finally" not in consumer_scene
    assert "Full HD-монитор" in consumer_scene
    assert "без чеклиста для разработки" in consumer_scene
    assert "резервный план" not in consumer_scene
    assert "доступ" not in consumer_scene.casefold()


def test_rewrite_chunked_dialogue_script_draft_falls_back_on_blocking_quality(
    monkeypatch,
) -> None:
    def fake_rewrite(*args, **kwargs):
        return """
mark: А по-человечески, первый заход.
nika: А по-человечески, второй заход.
gleb: А по-человечески, третий заход.
artem: А по-человечески, четвёртый заход.
"""

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", fake_rewrite)

    draft = """
### 1. @src #1
Fact lock:
- Main claim: Discord массово сбоит
- Allowed fact: Discord не запускается ни на одной платформе
"""

    script_text, validation = scriptwriter.rewrite_chunked_dialogue_script_draft(draft)

    assert validation.has_blocking_issues is False
    assert "а по-человечески" not in script_text.casefold()
    assert "Discord массово сбоит" in script_text


def test_deterministic_dialogue_fallback_has_scene_variety() -> None:
    blocks = [
        """
### 1. @src #1
Fact lock:
- Main claim: GitHub снизил доступность
- Allowed fact: OONI зафиксировал снижение доступности GitHub в России
""",
        """
### 2. @src #2
Fact lock:
- Main claim: Discord массово сбоит
- Allowed fact: Discord не запускается ни на одной платформе
""",
        """
### 3. @src #3
Fact lock:
- Main claim: У ИИ-агентов появилась библиотека памяти
- Allowed fact: Memoir превращает память Claude Code в библиотеку знаний
""",
    ]

    script_text = scriptwriter._build_deterministic_dialogue_from_blocks(blocks)

    assert "По исходной новости" not in script_text
    assert "Открываем конкретикой" in script_text
    assert "Следом история про практику" in script_text
    assert "Теперь к новости с подвохом" in script_text
    assert "микрофон" in script_text or "клавиатура" in script_text
    assert "После выпуска проверьте" in script_text
    assert script_text.count("mark:") >= 2
    assert script_text.count("nika:") >= 2
    assert script_text.count("gleb:") >= 2
    assert script_text.count("artem:") >= 2


def test_chunk_user_prompt_warns_against_forced_consumer_risk() -> None:
    prompt = scriptwriter._build_chunk_user_prompt("### 1. Test", 1, 1)

    assert "consumer/gadget/lifestyle" in prompt
    assert "production-риск" in prompt


def test_edit_dialogue_script_uses_editor_prompt(monkeypatch) -> None:
    fake_client = FakeClient()
    monkeypatch.setattr(scriptwriter, "create_llm_client", lambda: fake_client)

    result = scriptwriter.edit_dialogue_script(
        "mark: Валидный сценарий.",
        source_draft="Исходная новость",
        model="local-model",
    )

    assert result == "Готовый сценарий"
    kwargs = fake_client.chat.completions.kwargs
    assert kwargs["model"] == "local-model"
    assert "шоураннер" in kwargs["messages"][0]["content"]
    assert "Исходная новость" in kwargs["messages"][1]["content"]
    assert "mark: Валидный сценарий." in kwargs["messages"][1]["content"]


def test_rewrite_report_like_scenes_rewrites_only_stiff_span(monkeypatch) -> None:
    calls = []

    def fake_rewrite(prompt, *args, **kwargs):
        calls.append(prompt)
        return """
mark: Discord лежит, и это уже факт, а не ощущение.
nika: Тогда первый вопрос простой: где команда общается, если основной чат недоступен?
gleb: Люблю аварии, которые сразу проверяют план коммуникации.
artem: Проверьте резервный канал и порядок эскалации до следующего сбоя.
"""

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", fake_rewrite)

    script_text = """
mark: Здесь важно проверить доступность Discord.
nika: Практический вывод: проверьте резервный канал.
gleb: Команде нужно зафиксировать порядок эскалации.
artem: Что проверить: кто отвечает за коммуникацию.
mark: На этом всё, это были главные новости на сегодня.
"""

    rewritten = scriptwriter.rewrite_report_like_scenes(script_text, source_draft="Discord сбоит")

    assert len(calls) == 1
    assert "четыре доклада подряд" in calls[0]
    assert "где команда общается" in rewritten
    assert "На этом всё" in rewritten
    assert "Здесь важно проверить" not in rewritten


def test_edit_validated_dialogue_script_accepts_valid_editor_output(monkeypatch) -> None:
    original_script = """
mark: Добрый день, сегодня девятое мая, и вы слушаете НикКаст с обзором главных новостей в мире айти. Разбираем сбой платформы и риск для команд.
nika: В выпуске коротко: сбой Discord, доступность GitHub и обновления голосовых моделей.
gleb: Сбой платформы звучит скучно ровно до момента, когда весь дежурный чат лежит рядом с платформой.
artem: Команде важно заранее иметь резервный канал связи и понятный порядок эскалации.
mark: На этом всё, это были главные новости на сегодня.
nika: Хорошего дня всем.
gleb: И пусть алерты сегодня молчат.
artem: До новых встреч.
"""
    edited_script = """
mark: Добрый день, сегодня девятое мая, и вы слушаете НикКаст с обзором главных новостей в мире айти. Проверяем, что ломается первым: сервисы или наши планы на релиз.
nika: В выпуске коротко: сбой Discord, доступность GitHub и обновления голосовых моделей.
gleb: Если дежурный чат лежит вместе с сервисом, это уже не коммуникация, а синхронное молчание.
artem: Для команды вывод простой: держите резервный канал связи и проверьте порядок эскалации до аварии.
mark: На этом всё, это были главные новости на сегодня.
nika: Хорошего дня всем.
gleb: И пусть алерты сегодня молчат.
artem: До новых встреч.
"""

    monkeypatch.setattr(scriptwriter, "edit_dialogue_script", lambda *args, **kwargs: edited_script)

    script_text, validation = scriptwriter.edit_validated_dialogue_script(
        original_script,
        source_draft="Черновик новостей",
        attempts=1,
    )

    assert validation.has_blocking_issues is False
    assert "синхронное молчание" in script_text


def test_edit_validated_dialogue_script_falls_back_to_original_on_invalid_editor_output(
    monkeypatch,
) -> None:
    original_script = """
mark: Добрый день, сегодня девятое мая, и вы слушаете НикКаст с обзором главных новостей в мире айти. Проверяем риск доступности сервисов.
nika: В выпуске коротко: сбой Discord и доступность GitHub.
gleb: Если чат лежит, команда внезапно вспоминает про резервный канал.
artem: Практический вывод: проверьте порядок эскалации и доступ к репозиториям.
mark: На этом всё, это были главные новости на сегодня.
nika: Хорошего дня всем.
gleb: Без ночных аварий, пожалуйста.
artem: До новых встреч.
"""

    monkeypatch.setattr(
        scriptwriter,
        "edit_dialogue_script",
        lambda *args, **kwargs: "Невалидный текст без speaker-префиксов.",
    )

    script_text, validation = scriptwriter.edit_validated_dialogue_script(
        original_script,
        source_draft="Черновик новостей",
        attempts=1,
    )

    assert validation.has_blocking_issues is False
    assert script_text == original_script
