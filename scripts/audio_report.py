import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.audio.inspection import format_audio_report, write_audio_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect generated audio files with ffprobe.")
    parser.add_argument("paths", nargs="+", help="Audio files to inspect.")
    parser.add_argument("--json-output", default=None, help="Optional JSON report path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = [Path(value) for value in args.paths]
    print(format_audio_report(paths))
    if args.json_output:
        report_path = write_audio_report(paths, Path(args.json_output))
        print(f"Saved JSON report to {report_path}")


if __name__ == "__main__":
    main()
