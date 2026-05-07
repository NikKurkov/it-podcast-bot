from abc import ABC, abstractmethod
from pathlib import Path


class BaseTTSProvider(ABC):
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        speaker: str,
        output_path: Path,
        sample_rate: int | None = None,
    ) -> Path:
        raise NotImplementedError
