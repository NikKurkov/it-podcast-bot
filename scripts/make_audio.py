import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.audio.assembler import assemble_podcast
from app.audio.dialogue import script_to_dialogue_lines
from app.audio.music import mix_background_music
from app.audio.tts import convert_wav_to_mp3, synthesize_dialogue_lines, synthesize_with_espeak
from app.config.settings import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create local TTS audio from a script markdown file.")
    parser.add_argument("--input", default="data/episodes/latest_llm_script.md")
    parser.add_argument("--wav-output", default="data/audio/latest_episode.wav")
    parser.add_argument("--mp3-output", default="data/audio/latest_episode.mp3")
    parser.add_argument("--lines-dir", default="data/audio/latest_episode_lines")
    parser.add_argument("--provider", choices=("silero", "espeak"), default=settings.tts_provider)
    parser.add_argument("--voice", default=settings.tts_voice)
    parser.add_argument("--speed", type=int, default=settings.tts_speed)
    parser.add_argument("--with-music", action="store_true", default=settings.audio_background_music)
    parser.add_argument("--music-volume", type=float, default=settings.audio_background_music_volume)
    parser.add_argument("--music-path", default=settings.audio_background_music_path)
    parser.add_argument("--no-mp3", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file does not exist: {input_path}")

    text = input_path.read_text(encoding="utf-8")
    if args.provider == "silero":
        dialogue_lines = script_to_dialogue_lines(text)
        if not dialogue_lines:
            raise SystemExit("No speakable dialogue lines found.")

        rendered_lines = asyncio.run(
            synthesize_dialogue_lines(
                dialogue_lines,
                Path(args.lines_dir),
            ),
        )
        wav_path = assemble_podcast(
            rendered_lines,
            Path(args.wav_output),
            pauses_ms=[line.pause_after_ms for line in dialogue_lines],
        )
        print(f"Saved WAV audio to {wav_path}")
        print(f"Rendered {len(rendered_lines)} Silero dialogue lines to {args.lines_dir}")
    else:
        wav_path = synthesize_with_espeak(
            text,
            Path(args.wav_output),
            voice=args.voice,
            speed=args.speed,
        )
        print(f"Saved WAV audio to {wav_path}")

    if args.with_music:
        music_output_path = Path(args.wav_output)
        clean_voice_path = music_output_path.with_name(f"{music_output_path.stem}_voice.wav")
        music_output_path.replace(clean_voice_path)
        wav_path = mix_background_music(
            clean_voice_path,
            music_output_path,
            music_path=Path(args.music_path) if args.music_path else None,
            music_volume=args.music_volume,
            sample_rate=settings.tts_sample_rate,
        )
        print(f"Mixed background music into {wav_path}")

    if not args.no_mp3:
        mp3_path = convert_wav_to_mp3(wav_path, Path(args.mp3_output))
        print(f"Saved MP3 audio to {mp3_path}")


if __name__ == "__main__":
    main()
