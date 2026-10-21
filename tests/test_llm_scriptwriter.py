from types import SimpleNamespace
import json

import pytest

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
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def __init__(self) -> None:
        self.chat = FakeChat()


def test_rewrite_script_draft_uses_chat_completions(monkeypatch) -> None:
    fake_client = FakeClient()
    monkeypatch.setattr(scriptwriter, "create_llm_client", lambda: fake_client)

    result = scriptwriter.rewrite_script_draft(
        "Черновик", model="local-model", system_prompt="System"
    )

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
unknown: Некорректный диктор.
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


def test_rewrite_validated_dialogue_script_draft_raises_after_attempts(monkeypatch) -> None:
    def fake_rewrite(*args, **kwargs):
        return """
mark: Сегодня смотрим на риск.
nika: А если по-человечески?
gleb: Я видел похожие истории.
unknown: Некорректный диктор.
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
unknown: Некорректный диктор.
nika: А если по-человечески?
gleb: Я видел похожие истории.
"""

    monkeypatch.setattr(scriptwriter, "rewrite_dialogue_script_draft", fake_rewrite)

    try:
        scriptwriter.rewrite_validated_dialogue_script_draft("Черновик", attempts=2)
    except RuntimeError as exc:
        assert "Unknown dialogue speaker" in str(exc)
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
    assert "Командам стоит" in script_text


def test_rewrite_chunked_dialogue_script_draft_generates_by_news_blocks(monkeypatch) -> None:
    calls = []

    def fake_rewrite(prompt, *args, **kwargs):
        calls.append(prompt)
        return '{"turns": [{"speaker": "mark", "text": "Смотрим на конкретный факт."}, {"speaker": "nika", "text": "Здесь важно не потерять смысл новости."}, {"speaker": "gleb", "text": "Красивый анонс не отменяет проверки."}, {"speaker": "artem", "text": "Практический вывод — фиксируем ограничения."}]}'

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
    assert "На этом всё" not in script_text


def test_rewrite_chunked_dialogue_script_draft_falls_back_on_blocking_quality(
    monkeypatch,
) -> None:
    def fake_rewrite(*args, **kwargs):
        return '{"turns": [{"speaker": "mark", "text": "А по-человечески, первый заход."}, {"speaker": "nika", "text": "А по-человечески, второй заход."}, {"speaker": "gleb", "text": "А по-человечески, третий заход."}, {"speaker": "artem", "text": "А по-человечески, четвёртый заход."}]}'

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", fake_rewrite)

    draft = """
### 1. @src #1
Fact lock:
- Main claim: Discord массово сбоит
- Allowed fact: Discord не запускается ни на одной платформе
"""

    script_text, validation = scriptwriter.rewrite_chunked_dialogue_script_draft(draft)

    assert validation.has_blocking_issues is False
    assert "а по-человечески" in script_text.casefold()
    assert "Discord массово сбоит" not in script_text


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
    assert "Отредактируй" in kwargs["messages"][0]["content"]
    assert "Исходная новость" in kwargs["messages"][1]["content"]
    assert "mark: Валидный сценарий." in kwargs["messages"][1]["content"]


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


def test_chunked_generation_does_not_hide_programming_errors(monkeypatch) -> None:
    import pytest

    def broken_rewrite(*args, **kwargs):
        raise TypeError("programming error")

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", broken_rewrite)
    with pytest.raises(TypeError, match="programming error"):
        scriptwriter.rewrite_chunked_dialogue_script_draft(
            "### 1. @src #1\nFact lock:\n- Main claim: GitHub обновил API\n",
        )


def test_compact_news_keeps_late_source_limitations():
    block = """### 1. @source #1
Fact lock:
- Main claim: Сервис объявил новый API
- Allowed fact: Поддерживаются запросы из Python

Сервис объявил новый API. Поддерживаются запросы из Python.
Ограничения описаны отдельно. Клиенты используют токены доступа.
Пока доступно только приглашённым, публичного запуска не было.
Source: https://example.com/story
"""
    compact = scriptwriter._compact_news_block(block)
    assert "Пока доступно только приглашённым, публичного запуска не было." in compact
    assert "https://example.com/story" in compact


def test_chunk_budgets_scale_to_requested_duration(monkeypatch):
    calls = []

    def rewrite(prompt, **kwargs):
        calls.append((prompt, kwargs))
        return '{"turns": [{"speaker": "mark", "text": "Сервис изменил API."}, {"speaker": "nika", "text": "Обсудим совместимость."}]}'

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", rewrite)
    draft = "\n\n".join(
        f"### {i}. @src #{i}\nFact lock:\n- Main claim: Новость {i} про API" for i in range(1, 6)
    )
    scriptwriter.rewrite_chunked_dialogue_script_draft(draft, chunk_size=1, target_minutes=12)
    assert len(calls) == 5
    assert all(kwargs["max_tokens"] > 650 for _, kwargs in calls)
    assert all("слов" in prompt and "по содержанию" in prompt for prompt, _ in calls)
    calls.clear()
    scriptwriter.rewrite_chunked_dialogue_script_draft(draft, chunk_size=1, target_minutes=2)
    assert all(kwargs["max_tokens"] <= 650 for _, kwargs in calls)


@pytest.mark.parametrize("explicit, expected", [(None, 0.6), (0.0, 0.0), (0.9, 0.9)])
def test_chunk_writer_uses_configured_temperature_unless_explicit(monkeypatch, explicit, expected):
    monkeypatch.setattr(scriptwriter.settings, "llm_script_temperature", 0.6)
    calls = []

    def generate(payload, **kwargs):
        calls.append(kwargs)
        return '{"turns": [{"speaker": "nika", "text": "Запуск пока не объявлен."}]}'

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    scriptwriter.rewrite_chunked_dialogue_script_draft(
        "### 1. Source\nЗапуск пока не объявлен.",
        temperature=explicit,
    )
    assert len(calls) == 1 and calls[0]["temperature"] == expected


def test_configured_temperature_change_invalidates_author_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(scriptwriter.settings, "llm_script_temperature", 0.6)
    temperatures = []

    def generate(payload, **kwargs):
        temperatures.append(kwargs["temperature"])
        return '{"turns": [{"speaker": "nika", "text": "Запуск пока не объявлен."}]}'

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    source = "### 1. Source\nЗапуск пока не объявлен."
    scriptwriter.rewrite_chunked_dialogue_script_draft(source, checkpoint_dir=tmp_path)
    scriptwriter.rewrite_chunked_dialogue_script_draft(source, checkpoint_dir=tmp_path)
    monkeypatch.setattr(scriptwriter.settings, "llm_script_temperature", 0.7)
    scriptwriter.rewrite_chunked_dialogue_script_draft(source, checkpoint_dir=tmp_path)
    assert temperatures == [0.6, 0.7]


@pytest.mark.parametrize("scale", [1, 1e307])
def test_planned_depth_controls_scene_budget_without_cutting_sources(monkeypatch, scale):
    from app.llm import scene_editor

    monkeypatch.setattr(
        scene_editor,
        "plan_scenes",
        lambda *a, **k: {
            1: {
                "index": 1,
                "direction": "Короткое обсуждение",
                "participants": ["nika"],
                "depth_weight": scale,
            },
            2: {
                "index": 2,
                "direction": "Содержательное углубление",
                "participants": ["gleb", "artem"],
                "depth_weight": 3 * scale,
            },
        },
    )
    budgets = []

    def generate(payload, **kwargs):
        budgets.append(kwargs["max_tokens"])
        return '{"turns": [{"speaker": "nika", "text": "Новость без выдуманных подробностей."}]}'

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    scriptwriter.rewrite_chunked_dialogue_script_draft(
        "### 1. Source\nПервая полная новость\n### 2. Source\nВторая полная новость",
        with_plan=True,
        chunk_size=1,
        target_minutes=12,
    )
    assert budgets[1] == 3 * budgets[0]


def test_chunk_context_separates_full_evidence_from_previous_conversation():
    import json

    source = "Полный источник. Важная оговорка в конце: выпуск ещё не состоялся."
    previous = "mark: Это предварительное предположение, а не новый факт."
    payload = json.loads(
        scriptwriter._build_chunk_user_prompt(
            source,
            2,
            3,
            target_words=250,
            previous_scene=previous,
        )
    )
    assert payload["source_material"] == source
    assert payload["previous_scene_for_continuity_only"] == previous
    assert previous not in payload["source_material"]
    assert payload["scene"] == {"index": 2, "total": 3}


def test_native_checkpoint_is_invalidated_when_gguf_changes(tmp_path, monkeypatch):
    first, second = tmp_path / "first.gguf", tmp_path / "second.gguf"
    first.write_bytes(b"first model")
    second.write_bytes(b"second model")
    monkeypatch.setattr(scriptwriter.settings, "local_llm_engine", "llamacpp")
    calls = []

    def generate(*args, **kwargs):
        calls.append(True)
        return '{"turns": [{"speaker": "mark", "text": "Полный источник остаётся основой разговора."}]}'

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)

    def run(path):
        monkeypatch.setattr(scriptwriter.settings, "llama_cpp_model_path", str(path))
        scriptwriter.rewrite_chunked_dialogue_script_draft(
            "### 1. Источник\nПолная новость.",
            checkpoint_dir=tmp_path / "scenes",
        )

    run(first)
    run(first)
    assert len(calls) == 1
    run(second)
    assert len(calls) == 2
    second.write_bytes(b"updated second model")
    run(second)
    assert len(calls) == 3


def test_native_requests_reserve_reasoning_tokens_without_cutting_sources(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(scriptwriter.settings, "local_llm_engine", "llamacpp")
    monkeypatch.setattr(scriptwriter.settings, "llama_cpp_reasoning_budget", 512)
    monkeypatch.setattr(scriptwriter.settings, "llm_reasoning_effort", "low")
    monkeypatch.setattr(scriptwriter.settings, "llm_model", "native-model")
    monkeypatch.setattr(scriptwriter, "create_llm_client", lambda: fake)
    scriptwriter.rewrite_script_draft(
        "Полный источник.", model="native-model", system_prompt="System", max_tokens=500
    )
    assert fake.chat.completions.kwargs["max_tokens"] == 1012
    assert fake.chat.completions.kwargs["messages"][1]["content"] == "Полный источник."


def test_native_context_batches_reserve_hidden_and_visible_output(monkeypatch):
    from app.llm.context_budget import full_text_batches

    monkeypatch.setattr(scriptwriter.settings, "local_llm_engine", "llamacpp")
    monkeypatch.setattr(scriptwriter.settings, "llama_cpp_reasoning_budget", 512)
    monkeypatch.setattr(scriptwriter.settings, "llm_reasoning_effort", "low")
    monkeypatch.setattr(scriptwriter.settings, "ollama_context_length", 3000)
    sources = ["x" * 2000, "y" * 2000]
    assert list(full_text_batches(sources, "".join, output_tokens=500)) == [
        [sources[0]],
        [sources[1]],
    ]


def test_per_stage_reasoning_override_has_its_own_output_reserve(monkeypatch):
    monkeypatch.setattr(scriptwriter.settings, "local_llm_engine", "llamacpp")
    monkeypatch.setattr(scriptwriter.settings, "llm_reasoning_effort", "none")
    monkeypatch.setattr(scriptwriter.settings, "llama_cpp_reasoning_budget", 512)
    fake_client = FakeClient()
    monkeypatch.setattr(scriptwriter, "create_llm_client", lambda: fake_client)
    scriptwriter.rewrite_script_draft(
        "Полный исходник.", system_prompt="Проверь.", max_tokens=100, reasoning_effort="high"
    )
    kwargs = fake_client.chat.completions.kwargs
    assert kwargs["reasoning_effort"] == "high"
    assert kwargs["max_tokens"] == 612


def test_truncated_author_is_saved_as_diagnostic_not_accepted_checkpoint(tmp_path, monkeypatch):
    fake_client = FakeClient()
    fake_client.chat.completions.create = lambda **kwargs: SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="mark: Незавершённый текст"), finish_reason="length"
            )
        ]
    )
    monkeypatch.setattr(scriptwriter, "create_llm_client", lambda: fake_client)
    with pytest.raises(RuntimeError, match="truncated"):
        scriptwriter.rewrite_chunked_dialogue_script_draft(
            "### 1. Новость\nПолный источник.",
            source_blocks=["Полный источник."],
            checkpoint_dir=tmp_path,
            with_review=False,
        )
    assert (tmp_path / "001_draft.raw.txt").read_text() == "mark: Незавершённый текст"
    assert not (tmp_path / "001_draft.json").exists()


@pytest.mark.parametrize(
    "response",
    [
        "Обычный монолог без участников.",
        "mark: Даже диалог обязан соответствовать JSON-протоколу.",
        '{"turns": [',
        "[]",
        '{"turns": []}',
        '{"turns": "text"}',
        '{"turns": ["text"]}',
        '{"turns": [{"speaker": "unknown", "text": "Новость."}]}',
        '{"turns": [{"speaker": "nika", "text": "   "}]}',
        '{"turns": [{"speaker": "nika", "text": 42}]}',
        '{"turns": [{"speaker": "nika", "text": "Один.\\nДва."}]}',
        '{"turns": [{"speaker": "nika"}]}',
        '{"turns": [{"speaker": "nika", "text": "Факт", "extra": true}]}',
    ],
)
def test_invalid_author_response_is_saved_but_never_checkpointed(tmp_path, monkeypatch, response):
    fake = FakeClient()
    fake.chat.completions.create = lambda **kwargs: SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=response), finish_reason="stop")]
    )
    monkeypatch.setattr(scriptwriter, "create_llm_client", lambda: fake)
    with pytest.raises(ValueError):
        scriptwriter.rewrite_chunked_dialogue_script_draft(
            "### 1. Источник\nПолный текст.", checkpoint_dir=tmp_path
        )
    assert (tmp_path / "001_draft.raw.txt").read_text() == response
    assert not (tmp_path / "001_draft.json").exists()


def test_author_schema_preserves_complete_turns_and_active_speaker_choice(tmp_path, monkeypatch):
    captured = {}
    text = "Точнее: C++ и A/B — не одно и то же. " + "Полная оговорка. " * 80
    response = json.dumps(
        {"turns": [{"speaker": "nika", "text": text.rstrip()}]}, ensure_ascii=False
    )
    fake = FakeClient()

    def generate(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=response), finish_reason="stop")
            ]
        )

    fake.chat.completions.create = generate
    monkeypatch.setattr(scriptwriter, "create_llm_client", lambda: fake)
    monkeypatch.setattr(scriptwriter, "get_active_character_keys", lambda: ["nika"])
    script, _ = scriptwriter.rewrite_chunked_dialogue_script_draft(
        "### 1. Источник\nПолный текст.", checkpoint_dir=tmp_path
    )
    assert script == f"nika: {text.rstrip()}"
    schema = captured["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["turns"]["items"]["properties"]["speaker"]["enum"] == ["nika"]
    assert "maxItems" not in schema["properties"]["turns"]
    assert (tmp_path / "001_draft.raw.txt").read_text() == response
    assert json.loads((tmp_path / "001_draft.json").read_text())["result"]["script"] == script
