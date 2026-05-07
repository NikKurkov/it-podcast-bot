from pathlib import Path

from app.audio.providers.base import BaseTTSProvider


class XTTSTTSProvider(BaseTTSProvider):
    async def synthesize(
        self,
        text: str,
        speaker: str,
        output_path: Path,
        sample_rate: int | None = None,
    ) -> Path:
        raise NotImplementedError("Provider xtts is not implemented yet")
