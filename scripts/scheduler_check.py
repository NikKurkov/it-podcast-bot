import argparse
import json
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show scheduler, dependency, and latest run status."
    )
    parser.add_argument(
        "--log-lines", type=int, default=30, help="How many scheduled log lines to show."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print("Podcast scheduler check:")
    _print_systemd_status()
    _print_tcp_status()
    _print_latest_run_report()
    _print_log_tail(args.log_lines)


def _print_systemd_status() -> None:
    print("")
    print("Systemd:")
    for unit in ("it-podcast-bot-proxy.service", "it-podcast-bot.timer", "it-podcast-bot.service"):
        print(f"  {unit}: {_systemctl_value(['is-active', unit])}")
    next_timer = _systemctl_value(
        ["list-timers", "it-podcast-bot.timer", "--no-pager", "--no-legend"]
    )
    if next_timer and next_timer != "unknown":
        print(f"  next: {' '.join(next_timer.split()[:4])}")


def _print_tcp_status() -> None:
    print("")
    print("TCP:")
    endpoints = []
    if settings.telegram_proxy_url:
        endpoints.append(("telegram_proxy", _endpoint_from_url(settings.telegram_proxy_url)))
    if settings.llm_base_url:
        endpoints.append(("llm", _endpoint_from_url(settings.llm_base_url)))
    for name, endpoint in endpoints:
        if endpoint is None:
            print(f"  {name}: skipped")
            continue
        host, port = endpoint
        status = "ok" if _tcp_ready(host, port) else "fail"
        print(f"  {name}: {status} ({host}:{port})")


def _print_latest_run_report() -> None:
    print("")
    print("Latest run:")
    report_path = PROJECT_ROOT / "data" / "logs" / "latest_run_report.json"
    if not report_path.exists():
        print("  missing: data/logs/latest_run_report.json")
        return
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"  invalid json: {exc}")
        return
    print(f"  status: {report.get('status')}")
    print(f"  created_at: {report.get('created_at')}")
    print(f"  package: {report.get('package')}")
    print(f"  selected: {report.get('selected_count')}/{report.get('requested_top')}")
    publish_result = report.get("publish_result") or {}
    if publish_result:
        print(
            f"  published: {publish_result.get('channel_id')} #{publish_result.get('message_id')}"
        )
    for check in report.get("publication_checks") or []:
        print(f"  gate {check.get('name')}: {check.get('status')} - {check.get('detail')}")
    if report.get("error"):
        print(f"  error: {report['error']}")


def _print_log_tail(lines_count: int) -> None:
    log_path = PROJECT_ROOT / "data" / "logs" / "scheduled_podcast.log"
    if lines_count <= 0 or not log_path.exists():
        return
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    print("")
    print(f"Log tail: {log_path}")
    for line in lines[-lines_count:]:
        print(f"  {line}")


def _systemctl_value(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["systemctl", "--user", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return str(exc)
    return (result.stdout or result.stderr).strip() or f"exit code {result.returncode}"


def _endpoint_from_url(value: str) -> tuple[str, int] | None:
    parsed = urlparse(value)
    if not parsed.hostname:
        return None
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed.hostname, port


def _tcp_ready(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=3.0):
            return True
    except OSError:
        return False


if __name__ == "__main__":
    main()
