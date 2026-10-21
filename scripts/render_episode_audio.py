import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.pipeline.episode_paths import resolve_episode_path
from app.pipeline.episode_history import is_published_episode
from app.pipeline.publication import refresh_rendered_package

from app.audio.assembler import assemble_podcast
from app.audio.dialogue import script_to_dialogue_lines
from app.audio.inspection import write_audio_report
from app.audio.music import mix_background_music
from app.audio.tts import convert_wav_to_mp3, synthesize_dialogue_lines
from app.config.settings import settings
from app.llm.runtime import release_local_models
from app.llm.pronunciation import prepare_dialogue_speech
from app.utils.locking import exclusive_lock
from app.podcast.script_quality import (
    build_script_quality_report,
    quality_gate_allows_tts,
    write_script_quality_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render or remix audio for an existing episode package."
    )
    parser.add_argument("--episode", default="latest", help="Episode directory or `latest`.")
    parser.add_argument("--provider", choices=("silero", "xtts"), default=settings.tts_provider)
    parser.add_argument(
        "--with-music", action="store_true", default=settings.audio_background_music
    )
    parser.add_argument(
        "--music-volume", type=float, default=settings.audio_background_music_volume
    )
    parser.add_argument("--music-path", default=settings.audio_background_music_path)
    parser.add_argument(
        "--remix-only",
        action="store_true",
        help="Reuse audio_voice.wav and only rebuild audio.wav/audio.mp3 with music.",
    )
    parser.add_argument(
        "--skip-quality-gate",
        action="store_true",
        help="Render audio even if script quality warnings would normally block TTS.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    episode_path = _resolve_episode_path(args.episode)
    with exclusive_lock(episode_path / ".package.lock", "This episode package is busy."):
        if is_published_episode(episode_path) or (episode_path / "telegram_publish.json").exists():
            raise SystemExit("Copy a published package before changing its audio.")
        _render(episode_path, args)


def _render(episode_path: Path, args: argparse.Namespace) -> None:
    script_path = episode_path / "llm_script.md"
    voice_path = episode_path / "audio_voice.wav"
    wav_path = episode_path / "audio.wav"
    mp3_path = episode_path / "audio.mp3"
    report_path = episode_path / "audio_report.json"

    if args.remix_only:
        if not voice_path.exists():
            raise SystemExit(f"Cannot remix without clean voice track: {voice_path}")
    else:
        if not script_path.exists():
            raise SystemExit(f"Episode has no llm_script.md: {script_path}")
        script_text = script_path.read_text(encoding="utf-8")
        quality_report = build_script_quality_report(script_text)
        write_script_quality_report(quality_report, episode_path / "script_quality_report.json")
        allowed, blocking = quality_gate_allows_tts(quality_report)
        if not allowed and not args.skip_quality_gate:
            raise SystemExit(
                "Script quality gate blocked TTS. "
                f"Blocking issues: {', '.join(blocking)}. "
                "Run `make podcast-script-check` or use --skip-quality-gate.",
            )
        dialogue_lines = script_to_dialogue_lines(script_text)
        if not dialogue_lines:
            raise SystemExit("No speakable dialogue lines found.")
        dialogue_lines = prepare_dialogue_speech(
            dialogue_lines, episode_path / "speech_pronunciation.json"
        )
        if settings.llm_release_before_tts:
            models = {
                settings.llm_model,
                settings.llm_fast_model,
                settings.llm_final_model,
                settings.llm_chunked_model,
                settings.llm_editorial_review_model,
            }
            generation_path = episode_path / "script_generation.json"
            if generation_path.is_file():
                recorded_model = json.loads(generation_path.read_text(encoding="utf-8")).get(
                    "model"
                )
                if isinstance(recorded_model, str):
                    models.add(recorded_model)
            release_local_models(
                {model for model in models if model}, base_url=settings.llm_base_url
            )
        rendered_lines = asyncio.run(
            synthesize_dialogue_lines(
                dialogue_lines,
                episode_path / "audio_lines",
                provider_name=args.provider,
            ),
        )
        assemble_podcast(
            rendered_lines,
            voice_path,
            pauses_ms=[line.pause_after_ms for line in dialogue_lines],
            sample_rate=settings.tts_sample_rate,
        )

    if args.with_music:
        mix_background_music(
            voice_path,
            wav_path,
            music_path=Path(args.music_path) if args.music_path else None,
            music_volume=args.music_volume,
            sample_rate=settings.tts_sample_rate,
        )
    else:
        shutil.copyfile(voice_path, wav_path)

    convert_wav_to_mp3(wav_path, mp3_path)
    report_paths = [wav_path, mp3_path]
    if voice_path.exists():
        report_paths.append(voice_path)
    write_audio_report(report_paths, report_path)

    refresh_rendered_package(
        episode_path,
        provider=None if args.remix_only else args.provider,
        with_music=args.with_music,
        music_volume=args.music_volume,
    )
    print(f"Rendered episode audio: {mp3_path}")


def _resolve_episode_path(value: str) -> Path:
    return resolve_episode_path(value, PROJECT_ROOT)


if __name__ == "__main__":
    main()
