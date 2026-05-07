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


def test_parse_channels_deduplicates_values() -> None:
    channels = _parse_channels("@durov,durov\npythonetc\n@pythonetc")

    assert channels == ["durov", "pythonetc"]


def test_parse_channels_supports_telegram_links() -> None:
    channels = _parse_channels(
        """
        https://t.me/xakep_ru
        t.me/pythonetc
        https://t.me/s/durov
        https://t.me/whackdoor/28252
        """,
    )

    assert channels == ["xakep_ru", "pythonetc", "durov", "whackdoor"]
