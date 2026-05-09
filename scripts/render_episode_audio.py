import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.audio.assembler import assemble_podcast
from app.audio.dialogue import script_to_dialogue_lines
from app.audio.inspection import write_audio_report
from app.audio.music import mix_background_music
from app.audio.tts import convert_wav_to_mp3, synthesize_dialogue_lines
from app.config.settings import settings
from app.podcast.script_quality import (
    build_script_quality_report,
    quality_gate_allows_tts,
    write_script_quality_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render or remix audio for an existing episode package.")
    parser.add_argument("--episode", default="latest", help="Episode directory or `latest`.")
    parser.add_argument("--provider", choices=("silero", "xtts"), default=settings.tts_provider)
    parser.add_argument("--with-music", action="store_true", default=settings.audio_background_music)
    parser.add_argument("--music-volume", type=float, default=settings.audio_background_music_volume)
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
        rendered_lines = asyncio.run(
            synthesize_dialogue_lines(
                dialogue_lines,
                episode_path / "audio_lines",
                provider_name=args.provider,
            ),
        )
        assemble_podcast(
            rendered_lines,
            voice_path if args.with_music else wav_path,
            pauses_ms=[line.pause_after_ms for line in dialogue_lines],
        )

    if args.with_music:
        mix_background_music(
            voice_path,
            wav_path,
            music_path=Path(args.music_path) if args.music_path else None,
            music_volume=args.music_volume,
            sample_rate=settings.tts_sample_rate,
        )
    elif args.remix_only:
        wav_path.write_bytes(voice_path.read_bytes())

    convert_wav_to_mp3(wav_path, mp3_path)
    report_paths = [wav_path, mp3_path]
    if voice_path.exists():
        report_paths.append(voice_path)
    write_audio_report(report_paths, report_path)

    print(f"Rendered episode audio: {mp3_path}")


def _resolve_episode_path(value: str) -> Path:
    if value != "latest":
        path = Path(value)
        return path if path.is_absolute() else PROJECT_ROOT / path

    episodes_dir = PROJECT_ROOT / "data" / "episodes"
    candidates = [path for path in episodes_dir.iterdir() if path.is_dir()]
    if not candidates:
        raise SystemExit("No episode packages found in data/episodes.")
    return max(candidates, key=lambda path: path.stat().st_mtime)


if __name__ == "__main__":
    main()
