import sys

import scripts.final_run as final_run


def test_final_run_defaults_come_from_settings(monkeypatch) -> None:
    monkeypatch.setattr(final_run.settings, "final_collect_limit", 31)
    monkeypatch.setattr(final_run.settings, "final_pool_limit", 123)
    monkeypatch.setattr(final_run.settings, "final_top_posts", 7)
    monkeypatch.setattr(sys, "argv", ["final_run.py"])

    args = final_run.parse_args()

    assert args.collect_limit == 31
    assert args.pool_limit == 123
    assert args.top == 7


def test_final_run_cli_overrides_settings(monkeypatch) -> None:
    monkeypatch.setattr(final_run.settings, "final_collect_limit", 31)
    monkeypatch.setattr(final_run.settings, "final_pool_limit", 123)
    monkeypatch.setattr(final_run.settings, "final_top_posts", 7)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "final_run.py",
            "--collect-limit",
            "10",
            "--pool-limit",
            "20",
            "--top",
            "3",
        ],
    )

    args = final_run.parse_args()

    assert args.collect_limit == 10
    assert args.pool_limit == 20
    assert args.top == 3
