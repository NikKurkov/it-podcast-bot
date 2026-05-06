from app.telegram_reader.channels import _parse_channels


def test_parse_channels_supports_lines_commas_and_comments() -> None:
    channels = _parse_channels(
        """
        @durov, pythonetc
        # comment
        whackdoor # inline comment
        """,
    )

    assert channels == ["durov", "pythonetc", "whackdoor"]
