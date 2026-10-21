"""Keep workstation credentials, model choices and databases out of test runs."""

from app.config.settings import Settings, settings

# This runs before test-module imports can construct the shared database engine.
# Mutate the shared settings object so all modules observe the same safe defaults.
defaults = Settings.model_construct()
for name in Settings.model_fields:
    setattr(settings, name, getattr(defaults, name))
settings.database_url = "sqlite://"
settings.llm_base_url = "http://127.0.0.1:1/v1"
