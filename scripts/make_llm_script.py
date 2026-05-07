import argparse
import sys
from pathlib import Path

from openai import APIConnectionError, InternalServerError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.llm.scriptwriter import (
    model_for_profile,
    rewrite_dialogue_script_draft,
    rewrite_script_draft,
)
from app.podcast.script_validation import format_validation_report, validate_dialogue_script


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rewrite a local script draft with a local LLM.")
    parser.add_argument("--input", default="data/episodes/latest_script.md")
    parser.add_argument("--output", default="data/episodes/latest_llm_script.md")
    parser.add_argument("--model", default=None, help=f"Override model. Default: {settings.llm_model}")
    parser.add_argument(
        "--profile",
        choices=("default", "fast", "final"),
        default="default",
        help="Model profile to use when --model is not set.",
    )
    parser.add_argument(
        "--dialogue",
        action="store_true",
        help="Generate a four-character dialogue script for multi-voice TTS.",
    )
    parser.add_argument("--no-validate", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        raise SystemExit(f"Input file does not exist: {input_path}")

    draft_text = input_path.read_text(encoding="utf-8")
    model = args.model or model_for_profile(args.profile)
    try:
        if args.dialogue:
            script_text = rewrite_dialogue_script_draft(draft_text, model=model)
        else:
            script_text = rewrite_script_draft(draft_text, model=model)
    except APIConnectionError as exc:
        raise SystemExit(
            "Could not connect to local LLM server.\n"
            f"Configured base URL: {settings.llm_base_url}\n\n"
            "For Ollama, install it, then run:\n"
            f"  ollama pull {model}\n"
            "  ollama serve\n\n"
            "Then retry:\n"
            "  make llm-script"
        ) from exc
    except InternalServerError as exc:
        message = str(exc)
        if "architectural feature absent" in message or "CUDA error" in message:
            raise SystemExit(
                "Local LLM server failed inside CUDA.\n"
                "On this machine GTX 1070 Ti can fail with current Ollama CUDA builds.\n\n"
                "Run Ollama in CPU-only mode in a separate terminal:\n"
                "  make ollama-cpu\n\n"
                "Then retry:\n"
                "  make llm-script"
            ) from exc
        raise

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(script_text + "\n", encoding="utf-8")
    print(f"Saved LLM script to {output_path}")

    if args.dialogue and not args.no_validate:
        validation = validate_dialogue_script(script_text)
        print(format_validation_report(validation))
        if validation.has_errors:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
