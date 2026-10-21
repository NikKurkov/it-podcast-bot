import httpx
import pytest

from app.llm import runtime


def test_unloads_only_project_models_from_local_server():
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "test"})
        if request.url.path == "/api/ps":
            return httpx.Response(
                200, json={"models": [{"name": "project:7b"}, {"name": "other:3b"}]}
            )
        return httpx.Response(200, json={"done": True})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert runtime.release_local_models(
            {"project:7b"}, base_url="http://127.0.0.1:11434/v1", client=client
        ) == ["project:7b"]
    assert [r.url.path for r in requests] == ["/api/version", "/api/ps", "/api/generate"]
    assert requests[-1].read() == b'{"model":"project:7b","keep_alive":0}'


def test_remote_endpoint_is_not_sent_native_management_requests():
    def unexpected(request):
        pytest.fail("Remote model management is outside local resource handling")

    with httpx.Client(transport=httpx.MockTransport(unexpected)) as client:
        assert (
            runtime.release_local_models(
                {"model"}, base_url="https://remote.example/v1", client=client
            )
            == []
        )


def test_unload_failure_blocks_tts_handoff():
    def respond(request):
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "test"})
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": [{"name": "project:7b"}]})
        return httpx.Response(500)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(RuntimeError, match="release"):
            runtime.release_local_models(
                {"project:7b"}, base_url="http://localhost:11434/v1", client=client
            )


def test_non_ollama_local_endpoint_is_left_alone():
    def respond(request):
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert (
            runtime.release_local_models(
                {"model"}, base_url="http://localhost:8080/v1", client=client
            )
            == []
        )


def test_untagged_name_releases_canonical_latest_model():
    posted = []

    def respond(request):
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "test"})
        if request.url.path == "/api/ps":
            return httpx.Response(
                200, json={"models": [{"name": "registry:5000/team/project:latest"}]}
            )
        posted.append(request.read())
        return httpx.Response(200, json={"done": True})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert runtime.release_local_models(
            {"registry:5000/team/project"}, base_url="http://localhost:11434/v1", client=client
        ) == ["registry:5000/team/project:latest"]
    assert len(posted) == 1


def test_uncertain_server_state_blocks_gpu_handoff():
    def respond(request):
        raise httpx.ReadTimeout("server overloaded", request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(RuntimeError, match="memory|server"):
            runtime.release_local_models(
                {"model"}, base_url="http://localhost:11434/v1", client=client
            )


def test_native_handoff_checks_model_identity_and_waits_for_unloaded_state(tmp_path, monkeypatch):
    model = tmp_path / "model.gguf"
    model.touch()
    monkeypatch.setattr(runtime.settings, "local_llm_engine", "llamacpp")
    monkeypatch.setattr(runtime.settings, "llama_cpp_model_path", str(model))
    monkeypatch.setattr(runtime.settings, "llm_model", "local-model")
    monkeypatch.setattr(runtime.settings, "llm_api_key", "private-test-token")
    states = iter([False, True])
    monkeypatch.setattr(runtime.time, "sleep", lambda _: None)

    def respond(request):
        assert request.url.path == "/props"
        assert request.headers["authorization"] == "Bearer private-test-token"
        return httpx.Response(200, json={"model_path": str(model), "is_sleeping": next(states)})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert runtime.release_local_models(
            {"local-model"}, base_url="http://localhost:11434/v1", client=client
        ) == ["local-model"]


def test_native_handoff_rejects_a_different_models_server(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime.settings, "local_llm_engine", "llamacpp")
    monkeypatch.setattr(runtime.settings, "llama_cpp_model_path", str(tmp_path / "ours.gguf"))

    def respond(request):
        return httpx.Response(
            200, json={"model_path": str(tmp_path / "another.gguf"), "is_sleeping": True}
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(RuntimeError, match="identity"):
            runtime.release_local_models(
                {"model"}, base_url="http://localhost:11434/v1", client=client
            )


def test_default_release_targets_only_configured_models(monkeypatch):
    monkeypatch.setattr(runtime.settings, "llm_model", "project:7b")
    requests = []

    def respond(request):
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "test"})
        if request.url.path == "/api/ps":
            return httpx.Response(
                200, json={"models": [{"name": "project:7b"}, {"name": "unrelated:7b"}]}
            )
        requests.append(request.read())
        return httpx.Response(200, json={"done": True})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert runtime.release_local_models(
            base_url="http://localhost:11434/v1", client=client
        ) == ["project:7b"]
    assert len(requests) == 1
