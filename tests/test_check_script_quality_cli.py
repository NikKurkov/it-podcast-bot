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
