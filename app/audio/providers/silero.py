import asyncio
import logging
from pathlib import Path
from typing import Any

from app.config.settings import settings
from app.audio.providers.base import BaseTTSProvider
from app.audio.pronunciation import apply_pronunciation_map

logger = logging.getLogger(__name__)


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
        model = self._get_model()
        if speaker not in model.speakers:
            raise ValueError(
                f"Unsupported Silero speaker: {speaker}. "
                f"Supported speakers: {', '.join(sorted(model.speakers))}",
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
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

        package = (
            Path(settings.silero_model_path).expanduser() if settings.silero_model_path else None
        )
        if package is not None and not package.is_file():
            raise RuntimeError("Configured local Silero model package is missing.")

        try:
            import torch
        except ImportError as exc:
            raise RuntimeError(
                "Silero TTS requires torch. Install a PyTorch build compatible with your Python "
                "version, then retry. Run `make setup` to create the unified Python 3.11 "
                "environment with CPU PyTorch.",
            ) from exc

        try:
            if self.device == "cpu":
                torch.set_num_threads(settings.tts_cpu_threads)
            logger.info("Loading Silero TTS model %s on %s", settings.silero_model_id, self.device)
            if package is not None:
                model = torch.package.PackageImporter(str(package)).load_pickle(
                    "tts_models", "model"
                )
            else:
                model, _ = torch.hub.load(
                    repo_or_dir="snakers4/silero-models",
                    model="silero_tts",
                    language="ru",
                    speaker=settings.silero_model_id,
                    trust_repo=True,
                )
            model.to(self.device)
        except Exception as exc:
            raise RuntimeError(f"Failed to load Silero TTS model: {exc}") from exc

        self._model = model
        return self._model


def prepare_silero_text(text: str) -> str:
    return apply_pronunciation_map(text)
