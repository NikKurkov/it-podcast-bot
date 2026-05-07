import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.audio.models import DialogueLine, RenderedLine
from app.audio.providers.base import BaseTTSProvider
from app.audio.providers.piper import PiperTTSProvider
from app.audio.providers.silero import SileroTTSProvider
from app.audio.providers.xtts import XTTSTTSProvider
from app.audio.voices import get_voice_config
from app.podcast.characters import resolve_character_key

_PROVIDER_CACHE: dict[str, BaseTTSProvider] = {}


def get_tts_provider(provider_name: str) -> BaseTTSProvider:
    normalized_name = provider_name.strip().lower()
    if normalized_name in _PROVIDER_CACHE:
        return _PROVIDER_CACHE[normalized_name]

    if normalized_name == "silero":
        provider: BaseTTSProvider = SileroTTSProvider()
    elif normalized_name == "piper":
        provider = PiperTTSProvider()
    elif normalized_name == "xtts":
        provider = XTTSTTSProvider()
    else:
        raise ValueError("Unknown TTS provider: " f"{provider_name}. Supported: silero, piper, xtts")

    _PROVIDER_CACHE[normalized_name] = provider
    return provider


async def synthesize_dialogue_lines(
    lines: list[DialogueLine],
    output_dir: Path,
) -> list[RenderedLine]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered_lines: list[RenderedLine] = []

    for index, line in enumerate(lines, start=1):
        character_key = resolve_character_key(line.speaker)
        voice_config = get_voice_config(character_key)
        provider = get_tts_provider(voice_config["provider"])
        audio_path = output_dir / f"{index:03d}_{character_key}.wav"
        rendered_path = await provider.synthesize(
            line.text,
            speaker=voice_config["speaker"],
            output_path=audio_path,
            sample_rate=voice_config.get("sample_rate"),
        )
        rendered_lines.append(
            RenderedLine(
                speaker=character_key,
                text=line.text,
                audio_path=rendered_path,
            ),
        )

    return rendered_lines


def synthesize_with_espeak(
    text: str,
    output_path: Path,
    voice: str = "ru",
    speed: int = 160,
) -> Path:
    if not shutil.which("espeak-ng"):
        raise RuntimeError("espeak-ng is not installed or not available in PATH.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    speakable_text = markdown_to_speech_text(text)
    if not speakable_text:
        raise RuntimeError("No speakable text found.")

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as text_file:
        text_file.write(speakable_text)
        text_path = Path(text_file.name)

    try:
        subprocess.run(
            [
                "espeak-ng",
                "-v",
                voice,
                "-s",
                str(speed),
                "-f",
                str(text_path),
                "-w",
                str(output_path),
            ],
            check=True,
        )
    finally:
        text_path.unlink(missing_ok=True)

    return output_path


def convert_wav_to_mp3(wav_path: Path, mp3_path: Path) -> Path:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not installed or not available in PATH.")

    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(wav_path),
            "-codec:a",
            "libmp3lame",
            "-qscale:a",
            "4",
            str(mp3_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return mp3_path


def markdown_to_speech_text(markdown: str) -> str:
    lines = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("```"):
            continue
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^\s*[-*]\s+", "", line)
        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
        line = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", line)
        line = re.sub(r"https?://\S+", "", line)
        line = line.replace("---", "")
        line = line.strip()
        if line:
            lines.append(line)

    return "\n".join(lines)
