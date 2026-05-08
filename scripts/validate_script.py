import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.podcast.script_validation import (
    format_validation_report,
    repair_dialogue_script_text,
    validate_dialogue_script,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a dialogue podcast script.")
    parser.add_argument("--input", default="data/episodes/latest_llm_script.md")
    parser.add_argument("--max-line-chars", type=int, default=450)
    parser.add_argument("--allow-missing-characters", action="store_true")
    parser.add_argument(
        "--repair-output",
        default=None,
        help="Write an auto-repaired script to this path before returning validation status.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file does not exist: {input_path}")

    script_text = input_path.read_text(encoding="utf-8")
    result = validate_dialogue_script(
        script_text,
        max_line_chars=args.max_line_chars,
        require_all_characters=not args.allow_missing_characters,
    )
    if args.repair_output:
        repaired_text = repair_dialogue_script_text(script_text, result)
        repair_path = Path(args.repair_output)
        repair_path.parent.mkdir(parents=True, exist_ok=True)
        repair_path.write_text(repaired_text + "\n", encoding="utf-8")
        result = validate_dialogue_script(
            repaired_text,
            max_line_chars=args.max_line_chars,
            require_all_characters=not args.allow_missing_characters,
        )
        print(f"Repaired script written to {repair_path}")

    print(format_validation_report(result))
    print(f"  lines: {result.lines_count}")
    print(f"  speakers: {', '.join(result.speakers) if result.speakers else '-'}")
    if result.has_blocking_issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
