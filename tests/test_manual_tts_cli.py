from argparse import Namespace

import pytest

from app.audio.models import DialogueLine
from scripts import make_audio, make_tts_sample


@pytest.mark.parametrize("module", [make_audio, make_tts_sample])
def test_manual_audio_prepares_then_unloads_and_uses_prepared_pauses(tmp_path, monkeypatch, module):
    script = tmp_path / "script.md"
    script.write_text("mark: Длинная исходная реплика.", encoding="utf-8")
    args = Namespace(
        input=str(script),
        provider="silero",
        lines_dir=str(tmp_path / "lines"),
        output=str(tmp_path / "audio.wav"),
        wav_output=str(tmp_path / "audio.wav"),
        mp3_output=str(tmp_path / "audio.mp3"),
        with_music=False,
        no_mp3=True,
        no_assemble=False,
    )
    monkeypatch.setattr(module, "parse_args", lambda: args)
    monkeypatch.setattr(module.settings, "llm_release_before_tts", True)
    calls = []
    prepared = [
        DialogueLine("mark", "Первая часть.", pause_after_ms=60),
        DialogueLine("mark", "Продолжение.", pause_after_ms=520),
    ]

    def prepare(lines, path):
        calls.append("pronunciation")
        assert path == tmp_path / "lines/speech_pronunciation.json"
        return prepared

    def release():
        calls.append("release")

    async def synthesize(lines, *args, **kwargs):
        calls.append("tts")
        assert lines == prepared
        return []

    def assemble(lines, output, **kwargs):
        calls.append("assemble")
        assert kwargs["pauses_ms"] == [60, 520]
        return output

    monkeypatch.setattr(module, "prepare_dialogue_speech", prepare)
    monkeypatch.setattr(module, "release_local_models", release)
    monkeypatch.setattr(module, "synthesize_dialogue_lines", synthesize)
    monkeypatch.setattr(module, "assemble_podcast", assemble)
    module.main()
    assert calls == ["pronunciation", "release", "tts", "assemble"]
