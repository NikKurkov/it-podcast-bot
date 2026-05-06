import sys
from pathlib import Path

from openai import APIConnectionError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.llm.client import create_llm_client


def main() -> None:
    client = create_llm_client()
    print("LLM config:")
    print(f"  base_url: {settings.llm_base_url}")
    print(f"  model: {settings.llm_model}")

    try:
        models = client.models.list()
    except APIConnectionError as exc:
        raise SystemExit(
            "Could not connect to local LLM server.\n"
            f"Configured base URL: {settings.llm_base_url}\n\n"
            "For Ollama, install it, then run:\n"
            f"  ollama pull {settings.llm_model}\n"
            "  ollama serve"
        ) from exc
    model_ids = [model.id for model in models.data]
    print(f"  models_available: {len(model_ids)}")
    if model_ids:
        print("  first_models:")
        for model_id in model_ids[:10]:
            print(f"    {model_id}")

    if settings.llm_model not in model_ids:
        print("")
        print(f"Warning: configured model is not listed: {settings.llm_model}")


if __name__ == "__main__":
    main()
