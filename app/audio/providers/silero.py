import asyncio
import logging
from pathlib import Path
from typing import Any

from app.config.settings import settings
from app.audio.providers.base import BaseTTSProvider

logger = logging.getLogger(__name__)

SILERO_RU_MODEL = "v4_ru"
SUPPORTED_SILERO_SPEAKERS = {"aidar", "baya", "kseniya", "xenia", "eugene"}


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
        logger.info("Generating Silero TTS: speaker=%s, output=%s", speaker, output_path)
        model.save_wav(
            text=text,
            speaker=speaker,
            sample_rate=sample_rate,
            audio_path=str(output_path),
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
                "version, then retry. For example, use a Python 3.12 venv for Silero if torch "
                "is not available for the current Python.",
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
