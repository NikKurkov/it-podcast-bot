import pytest
import httpx

from scripts import start_llm_server


@pytest.fixture
def native_server(tmp_path, monkeypatch):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"fixture")
    monkeypatch.setattr(start_llm_server.settings, "local_llm_engine", "llamacpp")
    monkeypatch.setattr(start_llm_server.settings, "llama_cpp_model_path", str(model))
    monkeypatch.setattr(start_llm_server, "resolve_executable", lambda: "/usr/bin/llama-server")
    return tmp_path


def test_optional_native_template_layers_and_threads(native_server, monkeypatch):
    template = native_server / "chat.jinja"
    template.write_text("{{ messages }}")
    monkeypatch.setattr(start_llm_server.settings, "llama_cpp_chat_template_file", str(template))
    monkeypatch.setattr(start_llm_server.settings, "llama_cpp_gpu_layers", 0)
    monkeypatch.setattr(start_llm_server.settings, "llama_cpp_threads", 3)
    command = start_llm_server.server_command()
    assert command[command.index("--chat-template-file") + 1] == str(template.resolve())
    assert command[command.index("--n-gpu-layers") + 1] == "0"
    assert command[command.index("--threads") + 1] == "3"
    assert command[command.index("--threads-batch") + 1] == "3"


def test_checkpoint_spacing_is_forwarded_to_environment_and_native_command(
    native_server, monkeypatch
):
    monkeypatch.setattr(start_llm_server.settings, "ollama_checkpoint_min_step", 1024)
    monkeypatch.setattr(start_llm_server.settings, "llm_base_url", "http://127.0.0.1:11434/v1")
    monkeypatch.setattr(start_llm_server.settings, "llm_api_key", "private-test-token")
    monkeypatch.setattr(start_llm_server.settings, "llama_cpp_backend_library", None)
    env = start_llm_server.server_environment()
    command = start_llm_server.server_command()
    assert env["LLAMA_ARG_CHECKPOINT_MIN_SPACING_NT"] == "1024"
    assert command[command.index("--checkpoint-min-step") + 1] == "1024"


def test_cpu_overrides_configured_native_gpu_layers(native_server, monkeypatch):
    monkeypatch.setattr(start_llm_server.settings, "llama_cpp_gpu_layers", 25)
    gpu_command = start_llm_server.server_command()
    assert gpu_command[gpu_command.index("--n-gpu-layers") + 1] == "25"
    command = start_llm_server.server_command(cpu=True)
    assert command.count("--n-gpu-layers") == 1
    assert command[command.index("--n-gpu-layers") + 1] == "0"


def test_native_options_none_preserve_existing_command(native_server, monkeypatch):
    for name in ("llama_cpp_chat_template_file", "llama_cpp_gpu_layers", "llama_cpp_threads"):
        monkeypatch.setattr(start_llm_server.settings, name, None)
    command = start_llm_server.server_command()
    assert not {"--chat-template-file", "--n-gpu-layers", "--threads", "--threads-batch"} & set(
        command
    )


def test_native_template_missing_at_launch_is_rejected(native_server, monkeypatch):
    monkeypatch.setattr(
        start_llm_server.settings,
        "llama_cpp_chat_template_file",
        str(native_server / "missing.jinja"),
    )
    with pytest.raises(ValueError, match="template"):
        start_llm_server.server_command()


def test_native_readiness_waits_for_loading_without_sending_generation(monkeypatch):
    monkeypatch.setattr(start_llm_server.settings, "local_llm_engine", "llamacpp")
    monkeypatch.setattr(start_llm_server.settings, "llm_base_url", "http://127.0.0.1:11434/v1")
    monkeypatch.setattr(start_llm_server.settings, "llm_api_key", "private-test-key")
    monkeypatch.setattr(start_llm_server.time, "sleep", lambda _: None)
    seen = []

    def respond(request):
        seen.append(request)
        return httpx.Response(503 if len(seen) == 1 else 200, json={"status": "ok"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        start_llm_server.wait_until_ready(client=client)
    assert len(seen) == 2
    assert all(r.method == "GET" and r.url.path == "/health" for r in seen)
    assert all(r.headers["authorization"] == "Bearer private-test-key" for r in seen)


def test_readiness_rejects_wrong_auth_without_retrying(monkeypatch):
    monkeypatch.setattr(start_llm_server.settings, "llm_base_url", "http://localhost:11434/v1")

    def respond(request):
        return httpx.Response(401, text="private-test-key")

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(RuntimeError, match="HTTP 401") as error:
            start_llm_server.wait_until_ready(client=client)
    assert "private-test-key" not in str(error.value)


def test_server_defaults_bound_memory_and_use_one_model_at_a_time(monkeypatch):
    monkeypatch.setattr(start_llm_server.settings, "llm_base_url", "http://127.0.0.1:11434/v1")
    monkeypatch.setattr(start_llm_server.settings, "ollama_memory_max_mb", 4096)
    monkeypatch.setattr(start_llm_server.settings, "ollama_swap_max_mb", 256)
    env = start_llm_server.server_environment()
    assert env["OLLAMA_MAX_LOADED_MODELS"] == "1"
    assert env["OLLAMA_NUM_PARALLEL"] == "1"
    assert env["OLLAMA_NO_CLOUD"] == "true"
    assert env["LLAMA_ARG_CACHE_RAM"] == "0"
    assert env["LLAMA_ARG_CTX_CHECKPOINTS"] == "0"
    assert "MemoryMax=4096M" in start_llm_server.resource_properties()
    assert "MemorySwapMax=256M" in start_llm_server.resource_properties()


def test_remote_endpoint_cannot_be_exposed_by_local_launcher(monkeypatch):
    monkeypatch.setattr(start_llm_server.settings, "llm_base_url", "https://remote.example/v1")
    with pytest.raises(ValueError, match="loopback"):
        start_llm_server.server_environment()


def test_launcher_does_not_bind_a_different_default_port_from_the_client(monkeypatch):
    monkeypatch.setattr(start_llm_server.settings, "llm_base_url", "http://localhost/v1")
    with pytest.raises(ValueError, match="explicit port"):
        start_llm_server.server_environment()


def test_manual_cpu_mode_disables_gpu_backends(monkeypatch):
    monkeypatch.setattr(start_llm_server.settings, "llm_base_url", "http://localhost:11434/v1")
    env = start_llm_server.server_environment(cpu=True)
    assert env["CUDA_VISIBLE_DEVICES"] == ""
    assert env["GGML_VK_VISIBLE_DEVICES"] == ""
    assert env["OLLAMA_VULKAN"] == "false"


def test_native_server_uses_one_text_model_bounded_reasoning_and_private_auth(
    tmp_path, monkeypatch
):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"fixture")
    monkeypatch.setattr(start_llm_server.settings, "local_llm_engine", "llamacpp")
    monkeypatch.setattr(start_llm_server.settings, "llama_cpp_model_path", str(model))
    monkeypatch.setattr(start_llm_server.settings, "llm_model", "local-model")
    monkeypatch.setattr(start_llm_server.settings, "llm_api_key", "private-test-token")
    monkeypatch.setattr(start_llm_server.settings, "llm_base_url", "http://127.0.0.1:11434/v1")
    monkeypatch.setattr(start_llm_server, "resolve_executable", lambda: "/usr/bin/llama-server")
    command = start_llm_server.server_command()
    assert command[command.index("--model") + 1] == str(model)
    assert command[command.index("--alias") + 1] == "local-model"
    assert command[command.index("--reasoning-budget") + 1] == "1024"
    assert command[command.index("--parallel") + 1] == "1"
    assert "--mmproj" not in command
    assert "private-test-token" not in command
    assert start_llm_server.server_environment()["LLAMA_API_KEY"] == "private-test-token"
