import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.audio.assembler import assemble_podcast
from app.audio.models import DialogueLine
from app.audio.tts import synthesize_dialogue_lines
from app.audio.voices import get_voice_config
from app.config.settings import settings


SAMPLE_DIALOGUE = [
    DialogueLine(
        speaker="boris",
        text="Коллеги, начнём с главного. Сегодня у нас новости про искусственный интеллект, безопасность и немного боли от обновлений.",
    ),
    DialogueLine(
        speaker="lena",
        text="О, боль от обновлений — это я люблю. Особенно когда нажал обновить, а потом обновился уже как личность.",
    ),
    DialogueLine(
        speaker="max",
        text="На самом деле, многие новости недели связаны с тем, как разработчики пытаются ускорить работу с моделями и инфраструктурой.",
    ),
    DialogueLine(
        speaker="ilya",
        text="И здесь важно не только ускорение. Нужно смотреть на стоимость вычислений, воспроизводимость и безопасность цепочки поставки.",
    ),
    DialogueLine(
        speaker="boris",
        text="Вот именно. А теперь давайте без восторженных лозунгов. Что из этого реально влияет на команды разработки?",
    ),
    DialogueLine(
        speaker="lena",
        text="Можно я сначала спрошу простым языком: нам теперь работать станет легче или просто появится ещё один инструмент, который надо настроить?",
    ),
    DialogueLine(
        speaker="max",
        text="Хороший вопрос. Давайте разберём по пунктам.",
    ),
    DialogueLine(
        speaker="ilya",
        text="Начнём с технических ограничений, потому что именно они обычно определяют, взлетит инструмент в продакшене или нет.",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a local multi-speaker TTS sample.")
    parser.add_argument("--output", default="data/audio/sample_podcast.wav")
    parser.add_argument("--lines-dir", default="data/audio/sample_episode")
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
    print(f"Saved podcast sample to {output_path}")


if __name__ == "__main__":
    main()
