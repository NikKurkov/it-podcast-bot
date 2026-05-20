from app.audio.tts import markdown_to_speech_text
from app.audio.providers.silero import prepare_silero_text


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


def test_prepare_silero_text_transcribes_common_english_terms() -> None:
    text = prepare_silero_text("OpenAI показала API для GitHub, Full HD и JSON.")

    assert "оупен-эй-ай" in text
    assert "эй-пи-ай" in text
    assert "гитхаб" in text
    assert "фул-эйч-ди" in text
    assert "джейсон" in text
