import argparse
import sys
from pathlib import Path

from openai import APIConnectionError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.llm.scriptwriter import rewrite_script_draft


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rewrite a local script draft with a local LLM.")
    parser.add_argument("--input", default="data/episodes/latest_script.md")
    parser.add_argument("--output", default="data/episodes/latest_llm_script.md")
    parser.add_argument("--model", default=None, help=f"Override model. Default: {settings.llm_model}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        raise SystemExit(f"Input file does not exist: {input_path}")

    draft_text = input_path.read_text(encoding="utf-8")
    try:
        script_text = rewrite_script_draft(draft_text, model=args.model)
    except APIConnectionError as exc:
        raise SystemExit(
            "Could not connect to local LLM server.\n"
            f"Configured base URL: {settings.llm_base_url}\n\n"
            "For Ollama, install it, then run:\n"
            f"  ollama pull {settings.llm_model}\n"
            "  ollama serve\n\n"
            "Then retry:\n"
            "  make llm-script"
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(script_text + "\n", encoding="utf-8")
    print(f"Saved LLM script to {output_path}")


if __name__ == "__main__":
    main()
