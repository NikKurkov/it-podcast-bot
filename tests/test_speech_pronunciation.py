import json
from dataclasses import replace

import pytest

from app.audio.models import DialogueLine
from app.config.settings import settings
from app.llm import pronunciation


@pytest.fixture
def speech(monkeypatch):
    monkeypatch.setattr(settings, "tts_auto_pronunciation", True)
    monkeypatch.setattr(pronunciation, "load_pronunciation_map", lambda: {})
    monkeypatch.setattr(pronunciation, "generation_settings", lambda model: {"model": model})
    calls = []

    def generate(text, **kwargs):
        batch = json.loads(text)
        calls.append((batch, kwargs))
        return json.dumps(
            {"replacements": [{"id": item["id"], "spoken": "нейрочип"} for item in batch]}
        )

    monkeypatch.setattr("app.llm.scriptwriter.rewrite_script_draft", generate)
    return calls


def test_occurrences_preserve_context_and_original(tmp_path, monkeypatch, speech):
    lines = [
        DialogueLine("host", "Quasar-Next не работает с ИИ, а ИИ — работает!", "calm", 810),
        DialogueLine("guest", "O’Reilly: C++ и C#.", None, 620),
    ]
    originals = list(lines)

    # Only foreign terms require a model; unsupported Cyrillic abbreviations are spelled.
    def contextual(text, **kwargs):
        batch = json.loads(text)
        speech.append(batch)
        names = {
            "Quasar-Next": "квейзар-некст",
            "O’Reilly": "оу-райли",
            "C++": "си плюс плюс",
            "C#": "си шарп",
        }
        rows = []
        for item in batch:
            spoken = names[item["term"]]
            rows.append({"id": item["id"], "spoken": spoken})
        return json.dumps({"replacements": rows})

    monkeypatch.setattr("app.llm.scriptwriter.rewrite_script_draft", contextual)
    result = pronunciation.prepare_dialogue_speech(lines, tmp_path / "speech.json")
    assert result == [
        replace(lines[0], text="квейзар-некст не работает с и-и, а и-и — работает!"),
        replace(lines[1], text="оу-райли: си плюс плюс и си шарп."),
    ]
    assert lines == originals
    assert all(set(item) == {"id", "term", "context"} for batch in speech for item in batch)
    assert (tmp_path / "spoken_script.md").read_text().startswith("host: квейзар-некст")
    record = json.loads((tmp_path / "speech.json").read_text())["result"]
    assert record["targets"][0]["term"] == "Quasar-Next"


def test_cache_and_input_model_invalidation(tmp_path, monkeypatch, speech):
    path = tmp_path / "speech.json"
    lines = [DialogueLine("host", "Quasar здесь.")]
    first = pronunciation.prepare_dialogue_speech(lines, path)
    assert pronunciation.prepare_dialogue_speech(lines, path) == first
    assert len(speech) == 1
    pronunciation.prepare_dialogue_speech([replace(lines[0], text="Quasar там.")], path)
    assert len(speech) == 2
    monkeypatch.setattr(settings, "llm_model", "another-model")
    pronunciation.prepare_dialogue_speech([replace(lines[0], text="Quasar там.")], path)
    assert len(speech) == 3


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{"id": "unknown", "spoken": "текст"}],
        [{"id": "0:0:6", "spoken": "Foreign"}],
        [{"id": "0:0:6", "spoken": "текст\nспикер"}],
        [{"id": "0:0:6", "spoken": "123"}],
        [{"id": "0:0:6", "spoken": "  "}],
        [{"id": "0:0:6", "spoken": "текст"}] * 2,
    ],
)
def test_invalid_response_rejected(tmp_path, monkeypatch, speech, rows):
    monkeypatch.setattr(
        "app.llm.scriptwriter.rewrite_script_draft",
        lambda *args, **kwargs: json.dumps({"replacements": rows}),
    )
    with pytest.raises(ValueError):
        pronunciation.prepare_dialogue_speech(
            [DialogueLine("host", "Quasar")], tmp_path / "speech.json"
        )
    assert not (tmp_path / "spoken_script.md").exists()


def test_cached_forms_revalidated(tmp_path, speech):
    path = tmp_path / "speech.json"
    lines = [DialogueLine("host", "Quasar")]
    pronunciation.prepare_dialogue_speech(lines, path)
    record = json.loads(path.read_text())
    record["result"]["replacements"][0]["spoken"] = "Latin"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        pronunciation.prepare_dialogue_speech(lines, path)
    assert len(speech) == 1


@pytest.mark.parametrize("automatic", [True, False])
def test_manual_identity_and_expansion_without_model(tmp_path, monkeypatch, speech, automatic):
    monkeypatch.setattr(settings, "tts_auto_pronunciation", automatic)
    monkeypatch.setattr(
        pronunciation,
        "load_pronunciation_map",
        lambda: {
            "Quasar": "квейзар",
            "Preserve Name": "Preserve Name",
            "ИИ": "искусственный интеллект",
        },
    )
    result = pronunciation.prepare_dialogue_speech(
        [DialogueLine("host", "Quasar, Preserve Name, ИИ.")], tmp_path / "speech.json"
    )
    assert result[0].text == "квейзар, Preserve Name, искусственный интеллект."
    assert speech == []


def test_disabled_unknown_terms_and_long_manual_expansion(tmp_path, monkeypatch, speech):
    monkeypatch.setattr(settings, "tts_auto_pronunciation", False)
    monkeypatch.setattr(
        pronunciation,
        "load_pronunciation_map",
        lambda: {"Long": ("очень длинное произношение " * 15).strip()},
    )
    lines = [DialogueLine("host", "Long Quasar ИИ.", "happy", 930)]
    result = pronunciation.prepare_dialogue_speech(lines, tmp_path / "speech.json")
    assert all(len(line.text) <= 170 for line in result)
    assert all(line.speaker == "host" and line.emotion == "happy" for line in result)
    assert result[-1].pause_after_ms == 930
    assert (
        " ".join(line.text for line in result)
        == pronunciation.apply_pronunciation_map(
            lines[0].text, pronunciation.load_pronunciation_map()
        ).strip()
    )
    assert speech == []


def test_model_failure_propagates(tmp_path, monkeypatch, speech):
    def fail(*args, **kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr("app.llm.scriptwriter.rewrite_script_draft", fail)
    with pytest.raises(RuntimeError, match="model unavailable"):
        pronunciation.prepare_dialogue_speech(
            [DialogueLine("host", "Quasar")], tmp_path / "speech.json"
        )


@pytest.mark.parametrize("spoken", ["а" * 161, "с МИР"])
def test_oversized_or_context_echo_rejected(tmp_path, monkeypatch, speech, spoken):
    def generate(text, **kwargs):
        batch = json.loads(text)
        assert (
            kwargs["response_format"]["json_schema"]["schema"]["properties"]["replacements"][
                "items"
            ]["properties"]["spoken"]["maxLength"]
            == 160
        )
        return json.dumps({"replacements": [{"id": batch[0]["id"], "spoken": spoken}]})

    monkeypatch.setattr("app.llm.scriptwriter.rewrite_script_draft", generate)
    with pytest.raises(ValueError):
        pronunciation.prepare_dialogue_speech(
            [DialogueLine("host", "с МИР")], tmp_path / "speech.json"
        )
    assert not (tmp_path / "speech.json").exists()
    assert not (tmp_path / "spoken_script.md").exists()


def test_identifier_digits_are_preserved_in_complete_targets(tmp_path, speech):
    assert [
        match.group()
        for match in pronunciation._TARGET.finditer(
            "GPT4 Alpha4 3Alpha FreeMyTV O’Reilly2 C++ C# 2026 1-2"
        )
    ] == ["GPT4", "Alpha4", "3Alpha", "FreeMyTV", "O’Reilly2", "C++", "C#"]
    pronunciation.prepare_dialogue_speech(
        [DialogueLine("host", "Alpha4 и 3Alpha, год 2026.")], tmp_path / "speech.json"
    )
    assert [item["term"] for batch, _ in speech for item in batch] == ["Alpha4", "3Alpha"]


@pytest.mark.parametrize(
    "term,expected",
    [
        ("ИИ", "и-и"),
        ("РФ", "эр-эф"),
        ("СССР", "эс-эс-эс-эр"),
    ],
)
def test_abbreviations_spelled_without_model_and_cached(tmp_path, speech, term, expected):
    path = tmp_path / "speech.json"
    lines = [DialogueLine("host", f"Это с {term}, без изменений.", "calm", 830)]
    result = pronunciation.prepare_dialogue_speech(lines, path)
    assert result == [replace(lines[0], text=f"Это с {expected}, без изменений.")]
    record = json.loads(path.read_text())
    assert record["result"]["targets"][0]["term"] == term
    assert record["result"]["replacements"][0]["spoken"] == expected
    # Cached deterministic terms cannot acquire model-generated semantic expansions.
    record["result"]["replacements"][0]["spoken"] = "искусственный интеллект"
    path.write_text(json.dumps(record))
    assert pronunciation.prepare_dialogue_speech(lines, path) == result
    assert speech == []
    assert json.loads(path.read_text())["result"]["replacements"][0]["spoken"] == expected


def test_pronounceable_caps_keep_phonetic_model_form(tmp_path, monkeypatch, speech):
    def generate(text, **kwargs):
        batch = json.loads(text)
        speech.append(batch)
        return json.dumps({"replacements": [{"id": batch[0]["id"], "spoken": "МИР"}]})

    monkeypatch.setattr("app.llm.scriptwriter.rewrite_script_draft", generate)
    assert (
        pronunciation.prepare_dialogue_speech(
            [DialogueLine("host", "МИР здесь")], tmp_path / "speech.json"
        )[0].text
        == "мир здесь"
    )
    assert len(speech) == 1


def test_multiword_names_grouped_with_exact_offsets(tmp_path, monkeypatch, speech):
    def generate(text, **kwargs):
        batch = json.loads(text)
        speech.append(batch)
        forms = {"Bank of America": "бэнк оф америка", "Free My": "фри май"}
        return json.dumps(
            {"replacements": [{"id": item["id"], "spoken": forms[item["term"]]} for item in batch]}
        )

    monkeypatch.setattr("app.llm.scriptwriter.rewrite_script_draft", generate)
    line = DialogueLine("host", "Нет Bank of America, затем Free My — и ИИ.", "calm", 720)
    path = tmp_path / "speech.json"
    result = pronunciation.prepare_dialogue_speech([line], path)
    assert result == [replace(line, text="Нет бэнк оф америка, затем фри май — и и-и.")]
    assert [item["term"] for batch in speech for item in batch] == ["Bank of America", "Free My"]
    for target in json.loads(path.read_text())["result"]["targets"]:
        assert line.text[target["start"] : target["end"]] == target["term"]
        assert target["id"] == f"0:{target['start']}:{target['end']}"


def test_grouping_stops_at_manual_identity(tmp_path, monkeypatch, speech):
    monkeypatch.setattr(
        pronunciation, "load_pronunciation_map", lambda: {"Manual Name": "Manual Name"}
    )
    result = pronunciation.prepare_dialogue_speech(
        [DialogueLine("host", "Free My Manual Name Bank of America")], tmp_path / "speech.json"
    )
    assert result[0].text == "нейрочип Manual Name нейрочип"
    assert [item["term"] for batch, _ in speech for item in batch] == ["Free My", "Bank of America"]


@pytest.mark.parametrize("manual", [{"TV": "ти-ви"}, {}])
def test_partial_manual_or_default_spelling_keeps_original_name_whole(
    tmp_path,
    monkeypatch,
    speech,
    manual,
):
    monkeypatch.setattr(pronunciation, "load_pronunciation_map", lambda: manual)

    def generate(text, **kwargs):
        batch = json.loads(text)
        speech.append(batch)
        assert [item["term"] for item in batch] == ["Free My TV"]
        return json.dumps({"replacements": [{"id": batch[0]["id"], "spoken": "фри май ти-ви"}]})

    monkeypatch.setattr("app.llm.scriptwriter.rewrite_script_draft", generate)
    original = DialogueLine("host", "Нет Free My TV, это важно.", "calm", 730)
    path = tmp_path / "speech.json"
    assert pronunciation.prepare_dialogue_speech([original], path) == [
        replace(original, text="Нет фри май ти-ви, это важно.")
    ]
    target = json.loads(path.read_text())["result"]["targets"][0]
    assert target["term"] == original.text[target["start"] : target["end"]] == "Free My TV"
    assert len(speech) == 1


@pytest.mark.parametrize(
    "entries,text,expected",
    [
        ({"Free My TV": "фри май ти-ви"}, "Free My TV", "фри май ти-ви"),
        ({"Free": "фри", "My": "май", "TV": "ти-ви"}, "Free My TV", "фри май ти-ви"),
        ({"Free My": "Free My", "TV": "ти-ви"}, "Free My TV", "Free My ти-ви"),
        ({"Free My TV": "Free My TV"}, "Free My TV", "Free My TV"),
    ],
)
def test_whole_manual_names_and_identities_remain_authoritative(
    tmp_path,
    monkeypatch,
    speech,
    entries,
    text,
    expected,
):
    monkeypatch.setattr(pronunciation, "load_pronunciation_map", lambda: entries)
    result = pronunciation.prepare_dialogue_speech(
        [DialogueLine("host", text)], tmp_path / "speech.json"
    )
    assert result[0].text == expected
    assert speech == []
