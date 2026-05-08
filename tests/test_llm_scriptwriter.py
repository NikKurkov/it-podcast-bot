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
    assert "Спасибо за внимание" in script_text


def test_rewrite_validated_dialogue_script_draft_retries_quality_warnings(monkeypatch) -> None:
    outputs = iter(
        [
            """
mark: Сегодня мы поговорим о практическом риске.
nika: А если по-человечески?
gleb: Я видел похожие истории.
artem: Здесь важно проверить доступы и план отката.
""",
            """
mark: Риск в этой новости не в громком анонсе, а в том, как команда будет проверять изменения.
nika: То есть завтра стоит понять, что именно меняется в рабочем процессе?
gleb: Я видел похожие истории: сначала обещают экономию времени, потом ищут владельца поломки.
artem: Команде нужен контроль доступа, журнал изменений и понятный план отката.
""",
        ],
    )
    seen_drafts = []

    def fake_rewrite(draft_text, *args, **kwargs):
        seen_drafts.append(draft_text)
        return next(outputs)

    monkeypatch.setattr(scriptwriter, "rewrite_dialogue_script_draft", fake_rewrite)

    script_text, validation = scriptwriter.rewrite_validated_dialogue_script_draft(
        "Черновик",
        attempts=2,
    )

    assert validation.has_quality_retry_issues is False
    assert "Сегодня мы поговорим" not in script_text
    assert "Редакторские замечания" in seen_drafts[1]


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
