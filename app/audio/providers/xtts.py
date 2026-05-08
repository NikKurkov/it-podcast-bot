import asyncio
import logging
from pathlib import Path
from typing import Any

from app.config.settings import settings
from app.audio.providers.base import BaseTTSProvider

logger = logging.getLogger(__name__)


class XTTSTTSProvider(BaseTTSProvider):
    def __init__(
        self,
        model_name: str | None = None,
        language: str | None = None,
        device: str | None = None,
    ) -> None:
        self.model_name = model_name or settings.xtts_model_name
        self.language = language or settings.xtts_language
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
        )

    def _synthesize_sync(
        self,
        text: str,
        speaker: str,
        output_path: Path,
    ) -> Path:
        speaker_wav = _resolve_speaker_wav(speaker)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        model = self._get_model()
        logger.info(
            "Generating XTTS-v2: speaker_wav=%s, language=%s, output=%s",
            speaker_wav,
            self.language,
            output_path,
        )
        model.tts_to_file(
            text=text,
            speaker_wav=str(speaker_wav),
            language=self.language,
            file_path=str(output_path),
        )
        return output_path

    def _get_model(self):
        if self._model is not None:
            return self._model

        try:
            from TTS.api import TTS
        except ImportError as exc:
            raise RuntimeError(
                "XTTS-v2 requires Coqui TTS. Install it in the TTS environment:\n"
                "  make setup\n\n"
                "Then provide reference voices in data/voices/xtts/*.wav or via XTTS_*_VOICE.",
            ) from exc

        try:
            logger.info("Loading XTTS model %s on %s", self.model_name, self.device)
            model = TTS(self.model_name).to(self.device)
        except Exception as exc:
            raise RuntimeError(f"Failed to load XTTS-v2 model: {exc}") from exc

        self._model = model
        return self._model


def _resolve_speaker_wav(speaker: str) -> Path:
    path = Path(speaker).expanduser()
    if not path.exists():
        path = Path(settings.xtts_voice_refs_dir) / f"{speaker}.wav"

    if not path.exists():
        raise RuntimeError(
            "XTTS-v2 needs a reference WAV for each character.\n"
            f"Missing speaker reference: {path}\n\n"
            "Create files like:\n"
            "  data/voices/xtts/mark.wav\n"
            "  data/voices/xtts/gleb.wav\n"
            "  data/voices/xtts/nika.wav\n"
            "  data/voices/xtts/artem.wav\n\n"
            "Use clean 6-20 second mono/stereo WAV samples with consent.",
        )

    return path
