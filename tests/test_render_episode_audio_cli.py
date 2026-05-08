import sys

import scripts.render_episode_audio as render_episode_audio


def test_render_episode_audio_parse_remix_latest(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["render_episode_audio.py", "--episode", "latest", "--with-music", "--remix-only"],
    )

    args = render_episode_audio.parse_args()

    assert args.episode == "latest"
    assert args.with_music is True
    assert args.remix_only is True
