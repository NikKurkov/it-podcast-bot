from pathlib import Path

import pytest

from scripts.install_scheduler import (
    TcpWait,
    _normalize_time,
    build_ollama_service_unit,
    build_proxy_service_unit,
    build_service_unit,
    build_timer_unit,
)


def test_build_service_unit_waits_for_proxy_and_llm() -> None:
    service = build_service_unit(
        project_root=Path("/repo"),
        python_path=Path("/repo/.venv/bin/python"),
        publish=True,
        waits=[
            TcpWait("127.0.0.1", 2080, 900),
            TcpWait("localhost", 11434, 120),
        ],
        proxy_service="it-podcast-bot-proxy.service",
        llm_service="it-podcast-bot-ollama.service",
    )

    assert "WorkingDirectory=/repo" in service
    assert "Environment=TTS_PROVIDER=xtts" in service
    assert "Wants=network-online.target it-podcast-bot-proxy.service it-podcast-bot-ollama.service" in service
    assert "After=network-online.target it-podcast-bot-proxy.service it-podcast-bot-ollama.service" in service
    assert "Requires=it-podcast-bot-ollama.service" in service
    assert "wait_for_tcp.py 127.0.0.1 2080 --timeout 900" in service
    assert "wait_for_tcp.py localhost 11434 --timeout 120" in service
    assert "Restart=on-failure" in service
    assert "RestartSec=15min" in service
    assert "make_podcast.py --with-music --tts-provider xtts --publish" in service
    assert "scheduled_podcast.log" in service


def test_build_service_unit_can_skip_publish() -> None:
    service = build_service_unit(
        project_root=Path("/repo"),
        python_path=Path("/repo/.venv/bin/python"),
        publish=False,
        waits=[],
    )

    assert "--publish" not in service


def test_build_timer_unit_uses_daily_time() -> None:
    timer = build_timer_unit("07:00")

    assert "OnCalendar=*-*-* 07:00:00" in timer
    assert "Persistent=true" in timer


def test_normalize_time_validates_24h_format() -> None:
    assert _normalize_time("7:5") == "07:05"

    with pytest.raises(SystemExit):
        _normalize_time("25:00")


def test_build_proxy_service_unit_restarts_proxy() -> None:
    service = build_proxy_service_unit("/usr/bin/tg-ws-proxy")

    assert service is not None
    assert "ExecStart=/usr/bin/tg-ws-proxy" in service
    assert "Restart=on-failure" in service
    assert "WantedBy=default.target" in service


def test_build_ollama_service_unit_runs_project_cpu_server() -> None:
    service = build_ollama_service_unit(Path("/repo"))

    assert "Description=Ollama CPU server for it-podcast-bot" in service
    assert "WorkingDirectory=/repo" in service
    assert "StopWhenUnneeded=yes" in service
    assert "ExecStart=/usr/bin/bash /repo/scripts/serve_ollama_cpu.sh" in service
    assert "Restart=on-failure" in service
    assert "WantedBy=default.target" in service
