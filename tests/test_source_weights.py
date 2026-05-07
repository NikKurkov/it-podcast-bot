from app.pipeline.source_weights import get_source_weight, load_source_weights


def test_load_source_weights_parses_values(tmp_path) -> None:
    path = tmp_path / "source_weights.txt"
    path.write_text(
        """
        # comment
        xakep_ru=1.2
        @whackdoor=0.8
        broken
        invalid=nope
        """,
        encoding="utf-8",
    )

    assert load_source_weights(str(path)) == {
        "xakep_ru": 1.2,
        "whackdoor": 0.8,
    }


def test_get_source_weight_defaults_to_one() -> None:
    assert get_source_weight("unknown", {"xakep_ru": 1.2}) == 1.0
    assert get_source_weight("@xakep_ru", {"xakep_ru": 1.2}) == 1.2
