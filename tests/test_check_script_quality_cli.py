import sys

import scripts.check_script_quality as check_script_quality


def test_check_script_quality_parse_fix_strict(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["check_script_quality.py", "--episode", "latest", "--fix", "--strict"],
    )

    args = check_script_quality.parse_args()

    assert args.episode == "latest"
    assert args.fix is True
    assert args.strict is True


def test_check_script_quality_main_reports_current_quality_fields(monkeypatch, tmp_path, capsys):
    episode = tmp_path / "data/episodes/example"
    episode.mkdir(parents=True)
    (episode / "llm_script.md").write_text("mark: Проверяем выпуск.\n", encoding="utf-8")
    monkeypatch.setattr(check_script_quality, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["check_script_quality.py", "--episode", "example"])

    check_script_quality.main()

    assert "tts_ready: True" in capsys.readouterr().out
