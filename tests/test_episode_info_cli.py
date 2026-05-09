import sys

import scripts.episode_info as episode_info


def test_episode_info_parse_latest(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["episode_info.py", "--episode", "latest"])

    args = episode_info.parse_args()

    assert args.episode == "latest"
