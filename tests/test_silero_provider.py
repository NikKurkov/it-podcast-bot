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


def test_direct_silero_preparation_preserves_numeric_meaning():
    from app.audio.providers.silero import prepare_silero_text

    assert prepare_silero_text("До 2% при обновлении до v3.11.") == (
        "До двух процентов при обновлении до ви три точка одиннадцать."
    )
    assert prepare_silero_text("В статье 85 НК указано 105 тысяч рублей.") == (
        "В статье восемьдесят пятой НК указано сто пять тысяч рублей."
    )



def test_silero_keeps_financial_year_currency_and_version_context():
    from app.audio.providers.silero import prepare_silero_text

    assert prepare_silero_text("Цена 43,9 млрд $, дата в 2028 финансовом году.") == (
        "Цена сорок три целых девять десятых миллиарда долларов, "
        "дата в две тысячи двадцать восьмом финансовом году."
    )
    assert prepare_silero_text("Python 3.12, версия 2.0, цена 10 000 ₽.") == (
        "пайтон три точка двенадцать, версия два точка ноль, цена десять тысяч рублей."
    )


def test_silero_normalizes_dotted_date_and_english_currency_grouping():
    from app.audio.providers.silero import prepare_silero_text

    assert prepare_silero_text("К 25.11.2026 ожидается цена $1,200.50.") == (
        "К двадцать пятому ноября две тысячи двадцать шестого года ожидается "
        "цена одна тысяча двести целых пятьдесят сотых доллара."
    )
