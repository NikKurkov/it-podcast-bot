from scripts import doctor


def test_native_server_check_uses_configured_launcher_not_system_ollama(monkeypatch):
    monkeypatch.setattr(doctor.settings, "llm_base_url", "http://127.0.0.1:11434/v1")
    monkeypatch.setattr(doctor.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(doctor, "resolve_executable", lambda: "/local/llama-server")
    monkeypatch.setattr(doctor, "server_command", lambda: ["/local/llama-server"])
    monkeypatch.setattr(doctor, "server_environment", lambda: {"LLAMA_API_KEY": "private-test-key"})
    checks = doctor._binary_checks()
    assert all(check.status == "ok" for check in checks)
    assert checks[-1].detail == "/local/llama-server"
    assert "private-test-key" not in repr(checks)
    assert not any(check.name == "ollama" for check in checks)


def test_invalid_local_server_config_is_reported_without_sensitive_exception(monkeypatch):
    monkeypatch.setattr(doctor.settings, "llm_base_url", "http://localhost:11434/v1")

    def fail():
        raise ValueError("private-test-key")

    monkeypatch.setattr(doctor, "resolve_executable", fail)
    checks = doctor._binary_checks()
    assert checks[-1].status == "error"
    assert "private-test-key" not in repr(checks)


def test_native_config_detects_stale_profile_aliases(monkeypatch):
    monkeypatch.setattr(doctor.settings, "local_llm_engine", "llamacpp")
    monkeypatch.setattr(doctor.settings, "llm_model", "new-local-alias")
    monkeypatch.setattr(doctor.settings, "llm_final_model", "old-local-alias")
    checks = doctor._config_checks()
    assert next(check for check in checks if check.name == "native_model_aliases").is_error


def test_invalid_cast_is_reported_without_crashing_tts_preflight(monkeypatch):
    monkeypatch.setattr(doctor.settings, "podcast_participants", "unknown")
    monkeypatch.setattr(doctor.settings, "tts_provider", "xtts")
    assert next(
        check for check in doctor._config_checks() if check.name == "podcast_participants"
    ).is_error
    doctor._tts_checks()


def test_unsupported_provider_is_reported_before_render(monkeypatch):
    monkeypatch.setattr(doctor.settings, "tts_provider", "piper")
    assert next(check for check in doctor._tts_checks() if check.name == "tts_provider").is_error
