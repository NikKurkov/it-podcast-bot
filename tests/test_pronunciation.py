from pathlib import Path

from app.audio.pronunciation import apply_pronunciation_map, load_pronunciation_map


def test_load_pronunciation_map_reads_config(tmp_path: Path) -> None:
    config_path = tmp_path / "pronunciation.txt"
    config_path.write_text(
        """
# comment
OpenAI = оупен-эй-ай
Hugging Face = хаггинг-фейс
bad line
""",
        encoding="utf-8",
    )

    pronunciation = load_pronunciation_map(config_path)

    assert pronunciation["OpenAI"] == "оупен-эй-ай"
    assert pronunciation["Hugging Face"] == "хаггинг-фейс"
    assert "bad line" not in pronunciation


def test_apply_pronunciation_map_prefers_longest_match() -> None:
    text = apply_pronunciation_map(
        "Hugging Face и API.",
        {
            "Face": "фейс",
            "Hugging Face": "хаггинг-фейс",
            "API": "эй-пи-ай",
        },
    )

    assert text == "хаггинг-фейс и эй-пи-ай."
