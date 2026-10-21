from pydantic import ValidationError
import pytest

from app.config.settings import Settings, settings
from app.llm.artifacts import fingerprint, generation_settings


@pytest.mark.parametrize(
    "values",
    [
        {"LLAMA_CPP_GPU_LAYERS": -1},
        {"LLAMA_CPP_THREADS": 0},
        {"OLLAMA_CHECKPOINT_MIN_STEP": -1},
    ],
)
def test_native_execution_options_reject_invalid_values(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_native_template_setting_requires_an_existing_file(tmp_path):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, LLAMA_CPP_CHAT_TEMPLATE_FILE=str(tmp_path / "missing.jinja"))


def test_checkpoint_spacing_preserves_default_and_allows_zero():
    assert Settings.model_fields["ollama_checkpoint_min_step"].default == 8192
    assert Settings(_env_file=None, OLLAMA_CHECKPOINT_MIN_STEP=0).ollama_checkpoint_min_step == 0
    assert Settings.model_fields["ollama_context_checkpoints"].default == 0


def test_native_template_setting_rejects_a_directory(tmp_path):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, LLAMA_CPP_CHAT_TEMPLATE_FILE=tmp_path)


def test_native_template_changes_invalidate_generation_fingerprint(tmp_path, monkeypatch):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"fixture")
    template = tmp_path / "chat.jinja"
    template.write_text("original template")
    monkeypatch.setattr(settings, "local_llm_engine", "llamacpp")
    monkeypatch.setattr(settings, "llama_cpp_model_path", str(model))
    monkeypatch.setattr(settings, "llama_cpp_chat_template_file", str(template))
    first = generation_settings("local")
    assert first["native_chat_template"]["path"] == str(template.resolve())
    assert first["native_chat_template"]["size"] == template.stat().st_size
    assert first["native_chat_template"]["mtime_ns"] == template.stat().st_mtime_ns
    assert fingerprint(first) == fingerprint(generation_settings("local"))
    template.write_text("updated longer template")
    assert fingerprint(first) != fingerprint(generation_settings("local"))
    other = tmp_path / "other.jinja"
    other.write_text(template.read_text())
    before_path_change = fingerprint(generation_settings("local"))
    monkeypatch.setattr(settings, "llama_cpp_chat_template_file", str(other))
    assert before_path_change != fingerprint(generation_settings("local"))
