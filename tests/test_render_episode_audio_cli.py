import sys

import scripts.render_episode_audio as render_episode_audio


def test_render_episode_audio_parse_remix_latest(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["render_episode_audio.py", "--episode", "latest", "--with-music", "--remix-only"],
    )

    args = render_episode_audio.parse_args()

    assert args.episode == "latest"
    assert args.with_music is True
    assert args.remix_only is True


def test_render_episode_audio_parse_skip_quality_gate(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["render_episode_audio.py", "--episode", "latest", "--skip-quality-gate"],
    )

    args = render_episode_audio.parse_args()

    assert args.skip_quality_gate is True


def test_render_unloads_configured_models_before_tts(tmp_path, monkeypatch):
    from argparse import Namespace

    (tmp_path / "llm_script.md").write_text("nika: Запуск пока не объявлен.")
    (tmp_path / "selected_posts.json").write_text("[]")
    (tmp_path / "script_generation.json").write_text('{"model": "saved-writer"}')
    monkeypatch.setattr(
        render_episode_audio.settings, "llm_editorial_review_model", "separate-reviewer"
    )
    calls = []

    def prepare(lines, path):
        calls.append(("pronunciation", None))
        return lines

    monkeypatch.setattr(render_episode_audio, "prepare_dialogue_speech", prepare)
    monkeypatch.setattr(
        render_episode_audio,
        "release_local_models",
        lambda models, **kwargs: calls.append(("release", models)),
    )
    monkeypatch.setattr(render_episode_audio.settings, "llm_release_before_tts", True)

    async def synthesize(*args, **kwargs):
        calls.append(("tts", None))
        return []

    monkeypatch.setattr(render_episode_audio, "synthesize_dialogue_lines", synthesize)
    monkeypatch.setattr(
        render_episode_audio,
        "assemble_podcast",
        lambda lines, output, **k: output.write_bytes(b"new voice"),
    )
    monkeypatch.setattr(render_episode_audio, "convert_wav_to_mp3", lambda *a, **k: None)
    monkeypatch.setattr(render_episode_audio, "write_audio_report", lambda *a, **k: None)
    render_episode_audio._render(
        tmp_path,
        Namespace(
            remix_only=False,
            with_music=False,
            skip_quality_gate=False,
            provider="xtts",
            music_volume=0.04,
        ),
    )
    assert [item[0] for item in calls] == ["pronunciation", "release", "tts"]
    assert render_episode_audio.settings.llm_final_model in calls[1][1]
    assert {"saved-writer", "separate-reviewer"} <= calls[1][1]


def test_render_respects_package_lock(tmp_path, monkeypatch):
    import pytest
    from argparse import Namespace
    from app.utils.locking import exclusive_lock

    monkeypatch.setattr(
        render_episode_audio, "parse_args", lambda: Namespace(episode=str(tmp_path))
    )
    with exclusive_lock(tmp_path / ".package.lock", "busy"):
        with pytest.raises(RuntimeError, match="busy"):
            render_episode_audio.main()


def test_remix_uses_latest_clean_voice_and_preserves_its_provider(tmp_path, monkeypatch):
    import json
    import shutil
    from argparse import Namespace

    script = tmp_path / "llm_script.md"
    script.write_text("nika: Первый текст.")
    (tmp_path / "selected_posts.json").write_text("[]")
    monkeypatch.setattr(render_episode_audio.settings, "llm_release_before_tts", False)

    async def synthesize(*args, **kwargs):
        return []

    monkeypatch.setattr(render_episode_audio, "synthesize_dialogue_lines", synthesize)
    monkeypatch.setattr(
        render_episode_audio,
        "assemble_podcast",
        lambda lines, output, **k: output.write_text(script.read_text()),
    )
    monkeypatch.setattr(
        render_episode_audio,
        "mix_background_music",
        lambda voice, output, **k: shutil.copyfile(voice, output),
    )
    monkeypatch.setattr(render_episode_audio, "convert_wav_to_mp3", shutil.copyfile)
    monkeypatch.setattr(
        render_episode_audio, "write_audio_report", lambda paths, output: output.write_text("[]")
    )
    args = Namespace(
        remix_only=False,
        with_music=True,
        skip_quality_gate=False,
        provider="xtts",
        music_volume=0.04,
        music_path=None,
    )
    render_episode_audio._render(tmp_path, args)
    script.write_text("nika: Второй текст.")
    args.with_music = False
    render_episode_audio._render(tmp_path, args)
    args.remix_only = args.with_music = True
    args.provider = "silero"
    render_episode_audio._render(tmp_path, args)
    assert (tmp_path / "audio.mp3").read_text() == "nika: Второй текст."
    assert json.loads((tmp_path / "metadata.json").read_text())["tts_provider"] == "xtts"
