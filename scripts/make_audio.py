import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.audio.tts import convert_wav_to_mp3, synthesize_with_espeak
from app.config.settings import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create local TTS audio from a script markdown file.")
    parser.add_argument("--input", default="data/episodes/latest_llm_script.md")
    parser.add_argument("--wav-output", default="data/audio/latest_episode.wav")
    parser.add_argument("--mp3-output", default="data/audio/latest_episode.mp3")
    parser.add_argument("--voice", default=settings.tts_voice)
    parser.add_argument("--speed", type=int, default=settings.tts_speed)
    parser.add_argument("--no-mp3", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file does not exist: {input_path}")

    text = input_path.read_text(encoding="utf-8")
    wav_path = synthesize_with_espeak(
        text,
        Path(args.wav_output),
        voice=args.voice,
        speed=args.speed,
    )
    print(f"Saved WAV audio to {wav_path}")

    if not args.no_mp3:
        mp3_path = convert_wav_to_mp3(wav_path, Path(args.mp3_output))
        print(f"Saved MP3 audio to {mp3_path}")


if __name__ == "__main__":
    main()
