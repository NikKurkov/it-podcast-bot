import asyncio
import logging
import re
from pathlib import Path
from typing import Any

from app.config.settings import settings
from app.audio.providers.base import BaseTTSProvider

logger = logging.getLogger(__name__)

SILERO_RU_MODEL = "v4_ru"
SUPPORTED_SILERO_SPEAKERS = {"aidar", "baya", "kseniya", "xenia", "eugene"}

_ENGLISH_TTS_REPLACEMENTS = {
    "ChatGPT": "чат-джи-пи-ти",
    "OpenAI": "оупен-эй-ай",
    "GitHub": "гитхаб",
    "GitLab": "гитлаб",
    "YouTube": "ютуб",
    "Google": "гугл",
    "Microsoft": "майкрософт",
    "Apple": "эпл",
    "Android": "андроид",
    "iOS": "ай-о-эс",
    "Claude": "клод",
    "Discord": "дискорд",
    "Docker": "докер",
    "Kubernetes": "кубернетис",
    "JavaScript": "джаваскрипт",
    "TypeScript": "тайпскрипт",
    "Python": "пайтон",
    "Linux": "линукс",
    "Windows": "виндоус",
    "Full HD": "фул-эйч-ди",
    "API": "эй-пи-ай",
    "SDK": "эс-ди-кей",
    "CLI": "си-эл-ай",
    "CPU": "си-пи-ю",
    "GPU": "джи-пи-ю",
    "LLM": "эл-эл-эм",
    "GPT": "джи-пи-ти",
    "HTML": "эйч-ти-эм-эл",
    "CSS": "си-эс-эс",
    "SQL": "эс-кью-эл",
    "JSON": "джейсон",
    "YAML": "ямл",
}


class SileroTTSProvider(BaseTTSProvider):
    def __init__(self, device: str | None = None) -> None:
        self.device = device or settings.tts_device
        self._model: Any | None = None

    async def synthesize(
        self,
        text: str,
        speaker: str,
        output_path: Path,
        sample_rate: int | None = None,
    ) -> Path:
        return await asyncio.to_thread(
            self._synthesize_sync,
            text,
            speaker,
            output_path,
            sample_rate or settings.tts_sample_rate,
        )

    def _synthesize_sync(
        self,
        text: str,
        speaker: str,
        output_path: Path,
        sample_rate: int,
    ) -> Path:
        if speaker not in SUPPORTED_SILERO_SPEAKERS:
            raise ValueError(
                f"Unsupported Silero speaker: {speaker}. "
                f"Supported speakers: {', '.join(sorted(SUPPORTED_SILERO_SPEAKERS))}",
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        model = self._get_model()
        prepared_text = prepare_silero_text(text)
        logger.info("Generating Silero TTS: speaker=%s, output=%s", speaker, output_path)
        model.save_wav(
            text=prepared_text,
            speaker=speaker,
            sample_rate=sample_rate,
            audio_path=str(output_path),
            put_accent=True,
            put_yo=True,
        )
        return output_path

    def _get_model(self):
        if self._model is not None:
            return self._model

        try:
            import torch
        except ImportError as exc:
            raise RuntimeError(
                "Silero TTS requires torch. Install a PyTorch build compatible with your Python "
                "version, then retry. Run `make setup` to create the unified Python 3.11 "
                "environment with CPU PyTorch.",
            ) from exc

        try:
            logger.info("Loading Silero TTS model %s on %s", SILERO_RU_MODEL, self.device)
            model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-models",
                model="silero_tts",
                language="ru",
                speaker=SILERO_RU_MODEL,
                trust_repo=True,
            )
            model.to(self.device)
        except Exception as exc:
            raise RuntimeError(f"Failed to load Silero TTS model: {exc}") from exc

        self._model = model
        return self._model


def prepare_silero_text(text: str) -> str:
    result = text
    for source, replacement in sorted(
        _ENGLISH_TTS_REPLACEMENTS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        pattern = re.compile(
            rf"(?<![A-Za-zА-Яа-яЁё]){re.escape(source)}(?![A-Za-zА-Яа-яЁё])",
            flags=re.IGNORECASE,
        )
        result = pattern.sub(replacement, result)
    return result
