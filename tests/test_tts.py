from app.audio.tts import markdown_to_speech_text


def test_markdown_to_speech_text_removes_markdown_and_links() -> None:
    text = markdown_to_speech_text(
        """
        # Title

        **Important** text
        - item with https://example.com/link
        [label](https://example.com)
        ---
        """,
    )

    assert "Title" in text
    assert "Important text" in text
    assert "https://" not in text
    assert "label" in text
    assert "---" not in text
