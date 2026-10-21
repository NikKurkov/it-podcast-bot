"""Small atomic checkpoints for expensive local generation."""

import hashlib
import json
from pathlib import Path


def generation_settings(model: str) -> dict:
    from app.config.settings import settings

    values = {
        "model": model,
        "endpoint": settings.llm_base_url,
        "reasoning_effort": settings.llm_reasoning_effort,
        "context": settings.ollama_context_length,
        "native_reasoning_budget": settings.llama_cpp_reasoning_budget
        if settings.local_llm_engine == "llamacpp"
        and (settings.llm_reasoning_effort or "").strip().lower() != "none"
        else None,
    }
    if settings.local_llm_engine == "llamacpp":
        path = Path(settings.llama_cpp_model_path or "").expanduser().resolve()
        stat = path.stat()
        values["native_model"] = {
            "path": str(path),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
        if settings.llama_cpp_chat_template_file is not None:
            template = Path(settings.llama_cpp_chat_template_file).expanduser().resolve()
            stat = template.stat()
            values["native_chat_template"] = {
                "path": str(template),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
    return values


def fingerprint(value: dict) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_checkpoint(path: Path | None, key: str) -> dict | None:
    if path is None or not path.exists():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (
        isinstance(record, dict)
        and record.get("fingerprint") == key
        and isinstance(record.get("result"), dict)
    ):
        return record["result"]
    return None


def save_checkpoint(path: Path | None, key: str, result: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps({"fingerprint": key, "result": result}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)
