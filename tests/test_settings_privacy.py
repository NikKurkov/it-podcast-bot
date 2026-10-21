from app.config.settings import Settings


def test_settings_representation_does_not_disclose_credentials():
    settings = Settings(
        _env_file=None,
        TELEGRAM_API_HASH="private-telegram-hash",
        LLM_API_KEY="private-api-key",
        TELEGRAM_PROXY_URL="socks5://private:password@localhost:1",
        DATABASE_URL="postgresql://private:password@localhost/db",
    )
    assert "private" not in repr(settings)
    assert "password" not in repr(settings)
