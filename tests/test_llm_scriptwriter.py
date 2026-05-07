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
