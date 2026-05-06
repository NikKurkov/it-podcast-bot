from app.telegram_reader.collector import _message_url


def test_message_url_for_public_channel() -> None:
    assert _message_url("durov", 123) == "https://t.me/durov/123"


def test_message_url_is_empty_for_private_or_invite_source() -> None:
    assert _message_url("https://t.me/+invite", 123) is None
    assert _message_url("+invite", 123) is None
