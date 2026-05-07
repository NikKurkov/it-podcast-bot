import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.audio.assembler import assemble_podcast
from app.audio.models import DialogueLine
from app.audio.music import mix_background_music
from app.audio.tts import synthesize_dialogue_lines
from app.audio.voices import get_voice_config
from app.config.settings import settings


SAMPLE_DIALOGUE = [
    DialogueLine(
        speaker="mark",
        text="Сегодня у нас история, которая началась как обычная IT-новость, а закончилась вопросами к безопасности всей цепочки поставки.",
    ),
    DialogueLine(
        speaker="nika",
        text="Обожаю, когда “мы просто обновили зависимость” превращается в “почему у нас прод смотрит в стену”.",
    ),
    DialogueLine(
        speaker="gleb",
        text="Потому что зависимости — это не зависимости. Это маленькие юридически независимые мины в вашем lock-файле.",
    ),
    DialogueLine(
        speaker="artem",
        text="Если серьёзно, здесь важен не сам пакет, а то, как команда контролирует транзитивные зависимости, сборку и права публикации.",
    ),
    DialogueLine(
        speaker="mark",
        text="Давайте восстановим цепочку событий. Сначала был релиз, потом первые жалобы, потом внезапный rollback.",
    ),
    DialogueLine(
        speaker="nika",
        text="То есть если перевести с инженерного на человеческий: всё работало, потом стало модно, потом стало страшно?",
    ),
    DialogueLine(
        speaker="gleb",
        text="Почти. Только между “модно” и “страшно” обычно ещё есть этап “мы это уже выкатили в прод”.",
    ),
    DialogueLine(
        speaker="artem",
        text="Именно поэтому в production важны наблюдаемость, воспроизводимые сборки и понятная политика обновления зависимостей.",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a local multi-speaker TTS sample.")
    parser.add_argument("--output", default="data/audio/sample_podcast.wav")
    parser.add_argument("--lines-dir", default="data/audio/sample_episode")
    parser.add_argument("--with-music", action="store_true", default=settings.audio_background_music)
    parser.add_argument("--music-volume", type=float, default=settings.audio_background_music_volume)
    parser.add_argument("--music-path", default=settings.audio_background_music_path)
    parser.add_argument("--no-assemble", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        rendered_lines = asyncio.run(
            synthesize_dialogue_lines(
                SAMPLE_DIALOGUE,
                Path(args.lines_dir),
            ),
        )
    except RuntimeError as exc:
        raise SystemExit(
            f"{exc}\n\n"
            "Silero setup hint:\n"
            "  1. Use a Python version supported by PyTorch, preferably Python 3.12.\n"
            "  2. Install torch, numpy and soundfile in that environment.\n"
            "  3. Re-run: python scripts/make_tts_sample.py\n"
        ) from exc

    print("Rendered lines:")
    for rendered_line in rendered_lines:
        print(f"  {rendered_line.audio_path}")

    if args.no_assemble:
        return

    pauses = [
        get_voice_config(line.speaker).get("pause_after_ms", line.pause_after_ms)
        for line in SAMPLE_DIALOGUE
    ]
    output_path = assemble_podcast(rendered_lines, Path(args.output), pauses_ms=pauses)
    if args.with_music:
        clean_voice_path = output_path.with_name(f"{output_path.stem}_voice.wav")
        output_path.replace(clean_voice_path)
        output_path = mix_background_music(
            clean_voice_path,
            Path(args.output),
            music_path=Path(args.music_path) if args.music_path else None,
            music_volume=args.music_volume,
            sample_rate=settings.tts_sample_rate,
        )
    print(f"Saved podcast sample to {output_path}")


if __name__ == "__main__":
    main()
