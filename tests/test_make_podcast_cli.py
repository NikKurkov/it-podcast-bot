import scripts.make_podcast as make_podcast


def test_default_speech_provider_comes_from_configuration(monkeypatch):
    monkeypatch.setattr(make_podcast.settings, "tts_provider", "silero")
    calls = []
    monkeypatch.setattr(make_podcast, "_run", lambda args: calls.append(args))
    monkeypatch.setattr("sys.argv", ["make_podcast.py", "--no-collect"])
    make_podcast.main()
    (command,) = calls
    assert command[command.index("--tts-provider") + 1] == "silero"


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


def test_preview_requests_short_duration_and_never_autopublishes(monkeypatch):
    calls = []
    monkeypatch.setattr(make_podcast, "_run", lambda args: calls.append(args))
    monkeypatch.setattr("sys.argv", ["make_podcast.py", "--preview"])
    make_podcast.main()
    (command,) = calls
    assert command[command.index("--target-minutes") + 1] == "2"
    assert "--no-publish" in command
