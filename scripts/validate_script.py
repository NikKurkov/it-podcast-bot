import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.podcast.script_validation import format_validation_report, validate_dialogue_script


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a dialogue podcast script.")
    parser.add_argument("--input", default="data/episodes/latest_llm_script.md")
    parser.add_argument("--max-line-chars", type=int, default=450)
    parser.add_argument("--allow-missing-characters", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file does not exist: {input_path}")

    result = validate_dialogue_script(
        input_path.read_text(encoding="utf-8"),
        max_line_chars=args.max_line_chars,
        require_all_characters=not args.allow_missing_characters,
    )
    print(format_validation_report(result))
    print(f"  lines: {result.lines_count}")
    print(f"  speakers: {', '.join(result.speakers) if result.speakers else '-'}")
    if result.has_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
