import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings

SERVICE_NAME = "it-podcast-bot.service"
TIMER_NAME = "it-podcast-bot.timer"
PROXY_SERVICE_NAME = "it-podcast-bot-proxy.service"
OLLAMA_SERVICE_NAME = "it-podcast-bot-ollama.service"


@dataclass(frozen=True)
class TcpWait:
    host: str
    port: int
    timeout_seconds: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install a user systemd timer for daily podcast generation.")
    parser.add_argument("--time", default="07:00", help="Daily start time in HH:MM format.")
    parser.add_argument("--dry-run", action="store_true", help="Print unit files without writing them.")
    parser.add_argument("--no-enable", action="store_true", help="Write units but do not enable/start the timer.")
    parser.add_argument(
        "--proxy-service-command",
        default=None,
        help=(
            "Command for a dedicated user service that starts the Telegram proxy. "
            "Defaults to tg-ws-proxy when TELEGRAM_PROXY_URL is configured and tg-ws-proxy is installed."
        ),
    )
    parser.add_argument(
        "--publish",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Publish the generated episode to TELEGRAM_PUBLISH_CHANNEL_ID.",
    )
    parser.add_argument(
        "--user-systemd-dir",
        type=Path,
        default=Path.home() / ".config" / "systemd" / "user",
        help="Directory for user systemd units.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start_time = _normalize_time(args.time)
    python_path = PROJECT_ROOT / ".venv" / "bin" / "python"
    waits = _default_tcp_waits()
    proxy_service_text = build_proxy_service_unit(_proxy_service_command(args.proxy_service_command))
    ollama_service_text = build_ollama_service_unit(PROJECT_ROOT)
    service_text = build_service_unit(
        project_root=PROJECT_ROOT,
        python_path=python_path,
        publish=args.publish,
        waits=waits,
        proxy_service=PROXY_SERVICE_NAME if proxy_service_text else None,
        llm_service=OLLAMA_SERVICE_NAME,
    )
    timer_text = build_timer_unit(start_time)

    service_path = args.user_systemd_dir / SERVICE_NAME
    timer_path = args.user_systemd_dir / TIMER_NAME
    proxy_service_path = args.user_systemd_dir / PROXY_SERVICE_NAME
    ollama_service_path = args.user_systemd_dir / OLLAMA_SERVICE_NAME
    if args.dry_run:
        if proxy_service_text:
            print(f"# {proxy_service_path}")
            print(proxy_service_text)
            print("")
        print(f"# {ollama_service_path}")
        print(ollama_service_text)
        print("")
        print(f"# {service_path}")
        print(service_text)
        print(f"\n# {timer_path}")
        print(timer_text)
        return

    args.user_systemd_dir.mkdir(parents=True, exist_ok=True)
    if proxy_service_text:
        proxy_service_path.write_text(proxy_service_text, encoding="utf-8")
    ollama_service_path.write_text(ollama_service_text, encoding="utf-8")
    service_path.write_text(service_text, encoding="utf-8")
    timer_path.write_text(timer_text, encoding="utf-8")

    if not args.no_enable:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        if proxy_service_text:
            subprocess.run(["systemctl", "--user", "enable", "--now", PROXY_SERVICE_NAME], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", TIMER_NAME], check=True)

    print(f"Installed {SERVICE_NAME} and {TIMER_NAME}.")
    print(f"Daily run time: {start_time}")
    print("Logs: data/logs/scheduled_podcast.log")


def build_service_unit(
    *,
    project_root: Path,
    python_path: Path,
    publish: bool,
    waits: list[TcpWait] | None = None,
    proxy_service: str | None = None,
    llm_service: str | None = None,
) -> str:
    script_path = project_root / "scripts" / "make_podcast.py"
    log_path = project_root / "data" / "logs" / "scheduled_podcast.log"
    command = [
        str(python_path),
        str(script_path),
        "--with-music",
        "--tts-provider",
        "xtts",
    ]
    if publish:
        command.append("--publish")

    wants = ["network-online.target"]
    after = ["network-online.target"]
    requires: list[str] = []
    if proxy_service:
        wants.append(proxy_service)
        after.append(proxy_service)
    if llm_service:
        wants.append(llm_service)
        requires.append(llm_service)
        after.append(llm_service)

    lines = [
        "[Unit]",
        "Description=Generate and publish NikCast daily podcast",
        f"Wants={' '.join(wants)}",
        f"After={' '.join(after)}",
        "StartLimitIntervalSec=2h",
        "StartLimitBurst=3",
        "",
        "[Service]",
        "Type=oneshot",
        f"WorkingDirectory={_unit_quote(project_root)}",
        "Environment=TTS_PROVIDER=xtts",
        f"StandardOutput=append:{_unit_quote(log_path)}",
        f"StandardError=append:{_unit_quote(log_path)}",
        "Restart=on-failure",
        "RestartSec=15min",
    ]
    if requires:
        lines.insert(4, f"Requires={' '.join(requires)}")
    for wait in waits or []:
        wait_command = [
            str(python_path),
            str(project_root / "scripts" / "wait_for_tcp.py"),
            wait.host,
            str(wait.port),
            "--timeout",
            str(wait.timeout_seconds),
        ]
        lines.append(f"ExecStartPre={_format_command(wait_command)}")
    lines.append(f"ExecStart={_format_command(command)}")
    lines.append("")
    return "\n".join(lines)


def build_ollama_service_unit(project_root: Path) -> str:
    script_path = project_root / "scripts" / "serve_ollama_cpu.sh"
    return "\n".join(
        [
            "[Unit]",
            "Description=Ollama CPU server for it-podcast-bot",
            "After=network-online.target",
            "Wants=network-online.target",
            "StopWhenUnneeded=yes",
            "",
            "[Service]",
            "Type=simple",
            f"WorkingDirectory={_unit_quote(project_root)}",
            f"ExecStart=/usr/bin/bash {_unit_quote(script_path)}",
            "Restart=on-failure",
            "RestartSec=10s",
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        ],
    )


def build_proxy_service_unit(command: str | None) -> str | None:
    if not command:
        return None
    return "\n".join(
        [
            "[Unit]",
            "Description=Telegram proxy for it-podcast-bot",
            "After=network-online.target",
            "Wants=network-online.target",
            "",
            "[Service]",
            "Type=simple",
            f"ExecStart={command}",
            "Restart=on-failure",
            "RestartSec=10s",
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        ],
    )


def build_timer_unit(start_time: str) -> str:
    return "\n".join(
        [
            "[Unit]",
            "Description=Run NikCast daily podcast pipeline",
            "",
            "[Timer]",
            f"OnCalendar=*-*-* {start_time}:00",
            "Persistent=true",
            "Unit=it-podcast-bot.service",
            "",
            "[Install]",
            "WantedBy=timers.target",
            "",
        ],
    )


def _default_tcp_waits() -> list[TcpWait]:
    waits = [_wait_from_url(settings.llm_base_url, timeout_seconds=120)]
    if settings.telegram_proxy_url:
        waits.insert(0, _wait_from_url(settings.telegram_proxy_url, timeout_seconds=900))
    return [wait for wait in waits if wait is not None]


def _proxy_service_command(value: str | None) -> str | None:
    if value:
        return value
    if not settings.telegram_proxy_url:
        return None
    command = shutil.which("tg-ws-proxy")
    return command


def _wait_from_url(value: str | None, *, timeout_seconds: int) -> TcpWait | None:
    if not value:
        return None
    parsed = urlparse(value)
    if not parsed.hostname:
        return None
    port = parsed.port or _default_port(parsed.scheme)
    if port is None:
        return None
    return TcpWait(host=parsed.hostname, port=port, timeout_seconds=timeout_seconds)


def _default_port(scheme: str) -> int | None:
    if scheme in {"http", "socks5", "socks4"}:
        return 80
    if scheme == "https":
        return 443
    return None


def _normalize_time(value: str) -> str:
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise SystemExit("Time must use HH:MM format, for example 07:00.")
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError as exc:
        raise SystemExit("Time must use HH:MM format, for example 07:00.") from exc
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise SystemExit("Time must be a valid 24-hour clock value.")
    return f"{hour:02d}:{minute:02d}"


def _format_command(parts: list[str]) -> str:
    return " ".join(_unit_quote(Path(part)) if "/" in part else _unit_quote(part) for part in parts)


def _unit_quote(value: str | Path) -> str:
    text = str(value)
    if text and not any(char.isspace() or char in {'"', "\\"} for char in text):
        return text
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


if __name__ == "__main__":
    main()
