import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.audio.voice_refs import format_voice_reference_report, inspect_xtts_voice_references


def parse_args() -> argparse.Namespace:
    return argparse.ArgumentParser(description="Inspect XTTS voice reference files.").parse_args()


def main() -> None:
    parse_args()
    print(format_voice_reference_report(inspect_xtts_voice_references()))


if __name__ == "__main__":
    main()
