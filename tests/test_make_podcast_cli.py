import scripts.make_podcast as make_podcast


def test_script_only_disables_publish_even_when_env_default_is_enabled(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(make_podcast, "_run", lambda args: calls.append(args))
    monkeypatch.setattr(
        "sys.argv",
        ["make_podcast.py", "--script-only", "--no-collect"],
    )

    make_podcast.main()

    command = calls[0]
    assert "--no-publish" in command
    assert "--publish" not in command
    assert "--with-audio" not in command
