from types import SimpleNamespace
import sys

import pytest

from app.audio.providers.silero import SileroTTSProvider
from app.config.settings import settings


def test_local_silero_package_does_not_contact_torch_hub(tmp_path, monkeypatch):
    package = tmp_path / "speech.pt"
    package.write_bytes(b"fixture")
    monkeypatch.setattr(settings, "silero_model_path", str(package))
    calls = []
    model = SimpleNamespace(to=lambda device: calls.append(("device", device)))

    class Importer:
        def __init__(self, path):
            calls.append(("package", path))

        def load_pickle(self, namespace, name):
            assert (namespace, name) == ("tts_models", "model")
            return model

    def no_hub(**kwargs):
        pytest.fail("Configured local speech must not request remote repository code.")

    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            package=SimpleNamespace(PackageImporter=Importer),
            hub=SimpleNamespace(load=no_hub),
            set_num_threads=lambda value: None,
        ),
    )
    assert SileroTTSProvider(device="cpu")._get_model() is model
    assert calls == [("package", str(package)), ("device", "cpu")]


def test_missing_configured_package_does_not_fall_back_to_download(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "silero_model_path", str(tmp_path / "missing.pt"))
    with pytest.raises(RuntimeError, match="missing"):
        SileroTTSProvider(device="cpu")._get_model()
