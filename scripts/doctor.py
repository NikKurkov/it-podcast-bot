import argparse
import asyncio
import importlib.util
import shutil
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.db.repositories.posts import count_posts
from app.db.repositories.sources import count_sources
from app.db.session import SessionLocal, init_db
from app.telegram_reader.channels import get_channels
from app.telegram_reader.client import create_telegram_client


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    detail: str = ""

    @property
    def is_error(self) -> bool:
        return self.status == "error"

    @property
    def is_warning(self) -> bool:
        return self.status == "warning"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run pre-flight checks for podcast generation.")
    parser.add_argument("--telegram", action="store_true", help="Connect to Telegram and check authorization.")
    parser.add_argument("--no-tcp", action="store_true", help="Skip local TCP checks for proxy and LLM.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    checks = run_doctor_checks(check_telegram=args.telegram, check_tcp=not args.no_tcp)
    _print_report(checks)
    if any(check.is_error for check in checks):
        raise SystemExit(1)


def run_doctor_checks(*, check_telegram: bool = False, check_tcp: bool = True) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    checks.extend(_config_checks())
    checks.extend(_filesystem_checks())
    checks.extend(_binary_checks())
    checks.extend(_tts_checks())
    checks.extend(_database_checks())
    checks.extend(_disk_checks())
    if check_tcp:
        checks.extend(_tcp_checks())
    if check_telegram:
        checks.append(asyncio.run(_telegram_authorization_check()))
    return checks


def _config_checks() -> list[DoctorCheck]:
    checks = [
        _configured("telegram_api_id", bool(settings.telegram_api_id)),
        _configured("telegram_api_hash", bool(settings.telegram_api_hash)),
        _configured("telegram_publish_channel_id", bool(settings.telegram_publish_channel_id)),
        _configured("podcast_title", bool(settings.podcast_title.strip())),
        _configured("llm_base_url", bool(settings.llm_base_url.strip())),
        _configured("llm_model", bool(settings.llm_model.strip())),
    ]
    channels = get_channels()
    checks.append(
        DoctorCheck(
            "telegram_channels",
            "ok" if channels else "error",
            f"{len(channels)} configured",
        ),
    )
    return checks


def _filesystem_checks() -> list[DoctorCheck]:
    paths = [
        ("channels_file", Path(settings.telegram_channels_file), True),
        ("exclude_keywords_file", Path(settings.exclude_keywords_file), False),
        ("source_weights_file", Path(settings.source_weights_file), False),
        ("project_venv", Path(".venv/bin/python"), True),
        ("podcast_cover_image", Path(settings.podcast_cover_image or ""), False),
    ]
    checks = [_path_check(name, path, required) for name, path, required in paths if str(path)]
    session_file = Path("data/sessions") / f"{settings.telegram_session_name}.session"
    checks.append(_path_check("telegram_session", session_file, required=True))
    return checks


def _binary_checks() -> list[DoctorCheck]:
    binaries = ["ffmpeg", "ffprobe", "ollama"]
    return [
        DoctorCheck(binary, "ok" if shutil.which(binary) else "error", shutil.which(binary) or "missing")
        for binary in binaries
    ]


def _tts_checks() -> list[DoctorCheck]:
    checks = [
        DoctorCheck("tts_provider", "ok", settings.tts_provider),
        DoctorCheck("torch", "ok" if importlib.util.find_spec("torch") else "error", "required for TTS"),
    ]
    if settings.tts_provider.strip().lower() == "xtts":
        checks.append(
            DoctorCheck(
                "coqui_tts",
                "ok" if importlib.util.find_spec("TTS") else "error",
                "required for XTTS-v2",
            ),
        )
    for character in ("mark", "gleb", "nika", "artem"):
        configured_path = getattr(settings, f"xtts_{character}_voice")
        voice_path = Path(configured_path) if configured_path else Path(settings.xtts_voice_refs_dir) / f"{character}.wav"
        checks.append(_path_check(f"xtts_voice_{character}", voice_path, required=settings.tts_provider == "xtts"))
    if settings.audio_background_music_path:
        checks.append(_path_check("background_music", Path(settings.audio_background_music_path), required=True))
    return checks


def _database_checks() -> list[DoctorCheck]:
    try:
        init_db()
        with SessionLocal() as session:
            return [
                DoctorCheck("database", "ok", settings.database_url),
                DoctorCheck("database_sources", "ok", str(count_sources(session))),
                DoctorCheck("database_posts", "ok", str(count_posts(session))),
            ]
    except Exception as exc:
        return [DoctorCheck("database", "error", str(exc))]


def _disk_checks() -> list[DoctorCheck]:
    usage = shutil.disk_usage(PROJECT_ROOT)
    free_gb = usage.free / 1024 / 1024 / 1024
    status = "ok" if free_gb >= 5 else "warning" if free_gb >= 1 else "error"
    return [DoctorCheck("disk_free", status, f"{free_gb:.1f} GB")]


def _tcp_checks() -> list[DoctorCheck]:
    checks = []
    proxy_endpoint = _proxy_endpoint(settings.telegram_proxy_url)
    if proxy_endpoint:
        checks.append(_tcp_check("telegram_proxy_tcp", *proxy_endpoint))
    if settings.llm_base_url:
        parsed = urlparse(settings.llm_base_url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if host:
            checks.append(_tcp_check("llm_tcp", host, port))
    return checks


async def _telegram_authorization_check() -> DoctorCheck:
    try:
        client = create_telegram_client()
        await client.connect()
        try:
            authorized = await client.is_user_authorized()
        finally:
            await client.disconnect()
        return DoctorCheck("telegram_authorized", "ok" if authorized else "error", "yes" if authorized else "no")
    except Exception as exc:
        return DoctorCheck("telegram_authorized", "error", str(exc))


def _configured(name: str, value: bool) -> DoctorCheck:
    return DoctorCheck(name, "ok" if value else "error", "configured" if value else "missing")


def _path_check(name: str, path: Path, required: bool) -> DoctorCheck:
    exists = path.exists()
    if exists:
        return DoctorCheck(name, "ok", str(path))
    return DoctorCheck(name, "error" if required else "warning", f"missing: {path}")


def _proxy_endpoint(proxy_url: str | None) -> tuple[str, int] | None:
    if not proxy_url:
        return None
    parsed = urlparse(proxy_url)
    if not parsed.hostname or not parsed.port:
        return None
    return parsed.hostname, parsed.port


def _tcp_check(name: str, host: str, port: int) -> DoctorCheck:
    try:
        with socket.create_connection((host, port), timeout=3.0):
            return DoctorCheck(name, "ok", f"{host}:{port}")
    except OSError as exc:
        return DoctorCheck(name, "error", f"{host}:{port} - {exc}")


def _print_report(checks: list[DoctorCheck]) -> None:
    print("Podcast doctor:")
    for check in checks:
        marker = {"ok": "OK", "warning": "WARN", "error": "ERROR"}[check.status]
        suffix = f" - {check.detail}" if check.detail else ""
        print(f"  [{marker}] {check.name}{suffix}")
    errors = sum(1 for check in checks if check.is_error)
    warnings = sum(1 for check in checks if check.is_warning)
    print("")
    print(f"Summary: {errors} error(s), {warnings} warning(s)")


if __name__ == "__main__":
    main()
