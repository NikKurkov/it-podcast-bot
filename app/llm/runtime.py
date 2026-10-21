"""Hand local GPU memory back before loading a speech model."""

import logging
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)


def release_local_models(
    models: set[str] | None = None,
    *,
    base_url: str | None = None,
    client: httpx.Client | None = None,
) -> list[str]:
    """Confirm model memory is released on this run's verified local server."""
    if models is None:
        models = {
            model
            for model in (
                settings.llm_model,
                settings.llm_fast_model,
                settings.llm_final_model,
                settings.llm_chunked_model,
                settings.llm_editorial_review_model,
            )
            if model
        }
    parsed = urlsplit(base_url or settings.llm_base_url)
    if not models or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        return []
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return []
    if client is None:
        with httpx.Client(trust_env=False, timeout=20) as local_client:
            return release_local_models(models, base_url=base_url, client=local_client)
    native = f"{parsed.scheme}://{parsed.netloc}"
    if settings.local_llm_engine == "llamacpp":
        return _wait_for_native_sleep(native, client)
    try:
        version = client.get(native + "/api/version")
    except httpx.ConnectError:
        return []
    except httpx.TransportError as exc:
        raise RuntimeError("Could not confirm local server memory state before TTS.") from exc
    if version.status_code == 404:
        return []
    try:
        version.raise_for_status()
        if not isinstance(version.json().get("version"), str):
            return []
        active = client.get(native + "/api/ps")
        active.raise_for_status()
        names = {item["name"] for item in active.json()["models"]}
        released = []

        def canonical(name):
            return name if ":" in name.rsplit("/", 1)[-1] else name + ":latest"

        requested = {canonical(name) for name in models}
        for model in sorted(name for name in names if canonical(name) in requested):
            result = client.post(native + "/api/generate", json={"model": model, "keep_alive": 0})
            result.raise_for_status()
            if result.json().get("done") is not True:
                raise ValueError("Model release was not confirmed")
            released.append(model)
        if released:
            logger.info(
                "Released %s local language model(s) before speech synthesis", len(released)
            )
        return released
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(
            "Could not release local model memory before TTS; generation stopped."
        ) from exc


def _wait_for_native_sleep(native: str, client: httpx.Client) -> list[str]:
    """Read-only handoff: the owned native server unloads on idle, without stopping its unit."""
    expected = Path(settings.llama_cpp_model_path or "").expanduser().resolve()
    deadline = time.monotonic() + settings.llama_cpp_idle_sleep_seconds + 20
    while time.monotonic() < deadline:
        try:
            response = client.get(
                native + "/props", headers={"Authorization": "Bearer " + settings.llm_api_key}
            )
            response.raise_for_status()
            state = response.json()
            if (
                not isinstance(state.get("model_path"), str)
                or Path(state["model_path"]).resolve() != expected
            ):
                raise RuntimeError("Local native model identity does not match this project.")
            if state.get("is_sleeping") is True:
                logger.info("Local native model is unloaded before speech synthesis")
                return [settings.llm_model]
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError("Could not verify native model memory before TTS.") from exc
        time.sleep(0.2)
    raise RuntimeError("Native model did not release memory before TTS; generation stopped.")
