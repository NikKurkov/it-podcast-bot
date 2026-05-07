import re
import shutil
import subprocess
import tempfile
from pathlib import Path


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
