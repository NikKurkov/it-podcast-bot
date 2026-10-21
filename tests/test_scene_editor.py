import json

import pytest

from app.llm import scene_editor, scriptwriter


@pytest.fixture(autouse=True)
def disable_implication_critic(monkeypatch):
    monkeypatch.setattr(scene_editor.settings, "llm_scene_critic_enabled", False)
    monkeypatch.setattr(scene_editor.settings, "ollama_context_length", 100000)


def test_implication_review_preserves_full_context_and_reuses_schema_prefix(monkeypatch, tmp_path):
    source = "Полный источник. " * 100 + "Оговорка в самом конце."
    script = "mark: Первый факт. Второй факт.\n\nnika: Уточняющий вопрос?"
    calls, formats, prefixes, paths = [], [], [], []

    def generate(payload, **kwargs):
        data = json.loads(payload)
        assert data["source"] == source
        assert data["dialogue_context"] == script
        assert list(data)[-1] == "candidate"
        calls.append(data["candidate"])
        formats.append(json.dumps(kwargs["response_format"], ensure_ascii=False))
        prefixes.append(payload.partition('"candidate":')[0])
        paths.append(kwargs["response_path"])
        schema = kwargs["response_format"]["json_schema"]["schema"]["properties"]["issues"]
        assert schema["maxItems"] == 1
        assert schema["items"]["properties"]["id"] == {"type": "integer", "minimum": 1}
        assert schema["items"]["properties"]["reason"]["maxLength"] == 600
        assert kwargs["max_tokens"] == 600
        assert (
            kwargs["reasoning_effort"] == scene_editor.settings.llm_source_review_reasoning_effort
        )
        if data["candidate"]["id"] == 2:
            return '{"issues": []}'
        return json.dumps(
            {"issues": [{"id": 1, "reason": "Частное условие распространено на весь продукт."}]}
        )

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    assert scene_editor.review_scene_implications(
        script, source, model="local", response_path=tmp_path / "critic.json"
    ) == [
        {
            "claim": "Первый факт. Второй факт.",
            "reason": "Частное условие распространено на весь продукт.",
        },
    ]
    assert calls == [
        {"id": 1, "speaker": "mark", "text": "Первый факт. Второй факт."},
        {"id": 2, "speaker": "nika", "text": "Уточняющий вопрос?"},
    ]
    assert formats[0] == formats[1] and prefixes[0] == prefixes[1]
    assert [path.name for path in paths] == ["critic_turn_1.json", "critic_turn_2.json"]


@pytest.mark.parametrize(
    "issues",
    [
        None,
        "bad",
        {},
        [None],
        [{"id": 99, "reason": "Нет подтверждения"}],
        [{"id": True, "reason": "Нет подтверждения"}],
        [{"id": 1, "reason": "Нет подтверждения"}] * 2,
        [{"id": 1, "reason": ""}],
        [{"id": 1, "reason": "  "}],
        [{"id": 1, "reason": 123}],
        [{"id": 1, "reason": "x" * 601}],
    ],
)
def test_implication_review_rejects_invalid_issues(monkeypatch, issues):
    monkeypatch.setattr(
        scriptwriter, "rewrite_script_draft", lambda *a, **k: json.dumps({"issues": issues})
    )
    with pytest.raises(ValueError):
        scene_editor.review_scene_implications(
            "mark: Проверяемая реплика.", "Полный источник.", model="local"
        )


def test_implication_review_rejects_non_object_response(monkeypatch):
    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", lambda *a, **k: "[]")
    with pytest.raises(ValueError):
        scene_editor.review_scene_implications(
            "mark: Проверяемая реплика.", "Полный источник.", model="local"
        )


def test_implication_review_keeps_full_reasons_for_every_turn(monkeypatch):
    script = "\n".join(f"mark: Утверждение {index}." for index in range(40))
    checked = []
    reason = "Существенная оговорка источника не отражена в этой реплике. " * 4

    def generate(payload, **kwargs):
        schema = kwargs["response_format"]["json_schema"]["schema"]["properties"]["issues"]
        assert schema["items"]["properties"]["reason"]["maxLength"] == 600
        identity = json.loads(payload)["candidate"]["id"]
        checked.append(identity)
        return json.dumps({"issues": [{"id": identity, "reason": reason}]})

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    result = scene_editor.review_scene_implications(script, "Полный источник.", model="local")
    assert checked == list(range(1, 41))
    assert len(result) == 40 and all(issue["reason"] == reason for issue in result)


def test_implication_review_rejects_a_different_known_turn_id(monkeypatch):
    monkeypatch.setattr(
        scriptwriter,
        "rewrite_script_draft",
        lambda *a, **k: json.dumps(
            {
                "issues": [{"id": 2, "reason": "Это замечание относится к другой реплике."}],
            }
        ),
    )
    with pytest.raises(ValueError, match="turn ID"):
        scene_editor.review_scene_implications(
            "mark: Первая мысль.\nnika: Вторая мысль.", "Полный источник.", model="local"
        )


def test_implication_issue_blocks_before_statement_proof(monkeypatch, tmp_path):
    monkeypatch.setattr(scene_editor.settings, "llm_scene_critic_enabled", True)
    calls = []

    def generate(payload, **kwargs):
        assert "candidate" in json.loads(payload), "Proof must not run after a critic issue"
        calls.append(kwargs["response_path"])
        return json.dumps(
            {"issues": [{"id": 1, "reason": "Перенос свойства на другого участника."}]}
        )

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    path = tmp_path / "audit.raw.json"
    result = scene_editor.audit_scene(
        "mark: У всех одинаковое свойство.",
        "Описан один вариант.",
        model="local",
        response_path=path,
    )
    assert len(calls) == 1 and calls[0] != path and "_implications" in calls[0].name
    assert result["supported_claims"] == [] and result["statements"] == []
    assert (
        result["unsupported_claims"]
        == result["implication_review"]
        == [
            {
                "claim": "У всех одинаковое свойство.",
                "reason": "Перенос свойства на другого участника.",
            },
        ]
    )


def test_empty_implication_review_still_requires_complete_statement_proof(monkeypatch):
    monkeypatch.setattr(scene_editor.settings, "llm_scene_critic_enabled", True)
    phases = []

    def generate(payload, **kwargs):
        data = json.loads(payload)
        if "candidate" in data:
            phases.append("critic")
            return '{"issues": []}'
        phases.append("proof")
        return json.dumps(
            {
                "statements": [
                    {
                        "id": 1,
                        "claim": "Запуск не объявлен.",
                        "status": "supported",
                        "evidence_ids": ["S1"],
                        "reason": "Прямое подтверждение.",
                    },
                ]
            }
        )

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    result = scene_editor.audit_scene(
        "mark: Запуск не объявлен.", "Запуск не объявлен.", model="local"
    )
    assert phases == ["critic", "proof"]
    assert result["supported_claims"] and not result["unsupported_claims"]


def test_targeted_editor_changes_only_affected_turns(monkeypatch):
    script = "  mark: Уже выпущен. Ещё одна мысль.\n\nника：  Неизменённая реакция.\n"
    feedback = [{"claim": "Уже выпущен.", "reason": "Запуск не объявлен"}]

    def generate(payload, **kwargs):
        data = json.loads(payload)
        assert data["script"] == script and data["source"] == "Запуск не объявлен."
        assert data["required_corrections"] == feedback
        schema = kwargs["response_format"]["json_schema"]["schema"]["properties"]["edits"]
        assert schema["items"]["properties"]["id"]["enum"] == [1]
        return json.dumps(
            {
                "edits": [{"id": 1, "text": "Запуск пока не объявлен. Ещё одна мысль."}],
                "unresolved_issues": [],
            }
        )

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    result = scene_editor.review_scene(
        script, "Запуск не объявлен.", model="local", target_words=100, feedback=feedback
    )
    assert result["script"] == (
        "  mark: Запуск пока не объявлен. Ещё одна мысль.\n\nника：  Неизменённая реакция.\n"
    )
    assert result["changes"] == ["Updated turn 1"]
    assert result["unresolved_issues"] == []


@pytest.mark.parametrize(
    "edits",
    [
        [],
        [{"id": 99, "text": "Исправлено."}],
        [{"id": 1, "text": "Исправлено."}] * 2,
        [{"id": True, "text": "Исправлено."}],
        [{"id": 1, "text": "  Уже выпущен.  "}],
        [{"id": 1, "text": ""}],
        [{"id": 1, "text": " \t "}],
        [{"id": 1, "text": "Исправлено.\nnika: Добавлено."}],
        [{"id": 1, "text": "mark: Исправлено."}],
    ],
)
def test_targeted_editor_rejects_invalid_or_unchanged_edits(monkeypatch, edits):
    monkeypatch.setattr(
        scriptwriter,
        "rewrite_script_draft",
        lambda *a, **k: json.dumps(
            {
                "edits": edits,
                "unresolved_issues": [],
            }
        ),
    )
    with pytest.raises(ValueError):
        scene_editor.review_scene(
            "mark: Уже выпущен.",
            "Запуск не объявлен.",
            model="local",
            target_words=100,
            feedback=[{"claim": "Уже выпущен."}],
        )


@pytest.mark.parametrize("claim", ["", "Отсутствующее утверждение"])
def test_editor_fallback_rejects_claimed_corrections_without_changed_script(monkeypatch, claim):
    monkeypatch.setattr(
        scriptwriter,
        "rewrite_script_draft",
        lambda *a, **k: json.dumps(
            {
                "script": "mark: Уже выпущен.",
                "changes": ["Исправлены три факта"],
                "unresolved_issues": [],
            }
        ),
    )
    with pytest.raises(ValueError, match="unchanged"):
        scene_editor.review_scene(
            "mark: Уже выпущен.",
            "Запуск не объявлен.",
            model="local",
            target_words=100,
            feedback=[{"claim": claim}],
        )


def test_targeted_editor_rejects_fake_whole_scene_success(monkeypatch):
    monkeypatch.setattr(
        scriptwriter,
        "rewrite_script_draft",
        lambda *a, **k: json.dumps(
            {
                "script": "mark: Уже выпущен.",
                "changes": ["Исправлены три факта"],
                "unresolved_issues": [],
            }
        ),
    )
    with pytest.raises(ValueError, match="edits"):
        scene_editor.review_scene(
            "mark: Уже выпущен.",
            "Запуск не объявлен.",
            model="local",
            target_words=100,
            feedback=[{"claim": "Уже выпущен."}],
        )


def test_targeted_editor_cannot_omit_one_of_multiple_affected_turns(monkeypatch):
    monkeypatch.setattr(
        scriptwriter,
        "rewrite_script_draft",
        lambda *a, **k: json.dumps(
            {
                "edits": [{"id": 1, "text": "Запуск пока не объявлен."}],
                "unresolved_issues": [],
            }
        ),
    )
    with pytest.raises(ValueError, match="every affected"):
        scene_editor.review_scene(
            "mark: Уже выпущен.\nnika: Дата завтра.",
            "Срок неизвестен.",
            model="local",
            target_words=100,
            feedback=[{"claim": "Уже выпущен."}, {"claim": "Дата завтра."}],
        )


@pytest.mark.parametrize(
    "text", ["Точнее: запуск пока не объявлен.", "Вопрос: когда объявят запуск?"]
)
def test_targeted_editor_preserves_prose_colon_openings(monkeypatch, text):
    monkeypatch.setattr(
        scriptwriter,
        "rewrite_script_draft",
        lambda *a, **k: json.dumps(
            {
                "edits": [{"id": 1, "text": text}],
                "unresolved_issues": [],
            }
        ),
    )
    result = scene_editor.review_scene(
        "mark: Уже выпущен.",
        "Запуск не объявлен.",
        model="local",
        target_words=100,
        feedback=[{"claim": "Уже выпущен."}],
    )
    assert result["script"] == "mark: " + text


def test_plan_covers_complete_sources_and_uses_configured_speakers(monkeypatch):
    calls = []

    def generate(payload, **kwargs):
        calls.append(payload)
        data = json.loads(payload)
        assert data["total_scenes"] == 2 and len(data["sources"]) == 1
        identity = data["sources"][0]["index"]
        assert identity == len(calls)
        schema = kwargs["response_format"]["json_schema"]["schema"]["properties"]["scenes"]
        assert schema["minItems"] == schema["maxItems"] == 1
        assert schema["items"]["properties"]["index"]["enum"] == [identity]
        scenes = [
            {
                "index": 1,
                "direction": "Уточнить механизм и границы применения",
                "participants": ["nika", "artem"],
                "depth_weight": 1,
            },
            {
                "index": 2,
                "direction": "Разобрать противоречие источников",
                "participants": ["gleb", "mark"],
                "depth_weight": 2,
            },
        ]
        return json.dumps({"scenes": [scenes[identity - 1]]})

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    source = "Полный текст " * 80 + "Существенная оговорка в самом конце."
    plans = scene_editor.plan_scenes([source, "Другая новость"], model="local")
    assert len(calls) == 2
    assert json.loads(calls[0])["sources"] == [{"index": 1, "source": source}]
    assert json.loads(calls[1])["sources"] == [{"index": 2, "source": "Другая новость"}]
    assert "Существенная оговорка в самом конце." in calls[0]
    assert plans[1]["participants"] == ["nika", "artem"]
    assert plans[2]["direction"] != plans[1]["direction"]


@pytest.mark.parametrize(
    "scenes",
    [
        [{"index": 99, "direction": "x", "participants": ["mark"], "depth_weight": 1}],
        [{"index": 1, "direction": "x", "participants": ["invented"], "depth_weight": 1}],
        [{"index": 1, "direction": "x", "participants": [], "depth_weight": 1}],
        [],
    ],
)
def test_invalid_plan_cannot_drop_sources_or_invent_speakers(monkeypatch, scenes):
    monkeypatch.setattr(
        scriptwriter, "rewrite_script_draft", lambda *a, **k: json.dumps({"scenes": scenes})
    )
    with pytest.raises(ValueError):
        scene_editor.plan_scenes(["Полная новость"], model="local")


def test_editor_returns_source_grounded_text_and_audit(monkeypatch):
    def generate(payload, **kwargs):
        assert "Выпуск не объявлен" in payload
        assert "Уже выпущен" in payload
        return json.dumps(
            {
                "script": "nika: Выпуск пока не объявлен.",
                "changes": ["Убрано неподтверждённое утверждение о запуске"],
                "unresolved_issues": [],
            }
        )

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    result = scene_editor.review_scene(
        "mark: Уже выпущен.", "Выпуск не объявлен", model="local", target_words=100
    )
    assert "пока не объявлен" in result["script"]
    assert result["changes"] and not result["unresolved_issues"]


def test_editor_rejects_unknown_speaker_even_if_model_claims_success(monkeypatch):
    monkeypatch.setattr(
        scriptwriter,
        "rewrite_script_draft",
        lambda *a, **k: json.dumps(
            {
                "script": "invented: Привет.",
                "changes": [],
                "unresolved_issues": [],
            }
        ),
    )
    with pytest.raises(ValueError, match="structural"):
        scene_editor.review_scene("mark: Привет.", "Новость", model="local", target_words=100)


def test_fact_audit_requires_verbatim_source_evidence(monkeypatch):
    monkeypatch.setattr(
        scriptwriter,
        "rewrite_script_draft",
        lambda *a, **k: json.dumps(
            {
                "statements": [
                    {
                        "id": 1,
                        "claim": "Запуск не объявлен.",
                        "status": "supported",
                        "evidence_ids": ["S1"],
                        "reason": "",
                    }
                ],
            }
        ),
    )
    result = scene_editor.audit_scene(
        "nika: Запуск не объявлен.", "Запуск не объявлен.", model="local"
    )
    assert not result["unsupported_claims"]


def test_fabricated_source_quote_does_not_pass_audit(monkeypatch):
    monkeypatch.setattr(
        scriptwriter,
        "rewrite_script_draft",
        lambda *a, **k: json.dumps(
            {
                "statements": [
                    {
                        "id": 1,
                        "claim": "Продукт меняет прошивку.",
                        "status": "supported",
                        "evidence_ids": ["S99"],
                        "reason": "",
                    }
                ],
            }
        ),
    )
    with pytest.raises(ValueError, match="evidence IDs"):
        scene_editor.audit_scene(
            "mark: Продукт меняет прошивку.", "Способ установки не описан.", model="local"
        )


def test_fact_audit_preserves_model_reported_unsupported_claim(monkeypatch):
    monkeypatch.setattr(
        scriptwriter,
        "rewrite_script_draft",
        lambda *a, **k: json.dumps(
            {
                "statements": [
                    {
                        "id": 1,
                        "claim": "Запуск завтра.",
                        "status": "unsupported",
                        "evidence_ids": [],
                        "reason": "Срок не указан",
                    }
                ],
            }
        ),
    )
    result = scene_editor.audit_scene("nika: Запуск завтра.", "Дата не объявлена.", model="local")
    assert result["unsupported_claims"][0]["claim"] == "Запуск завтра."


def test_audit_rejects_unbounded_justification_instead_of_accepting_a_runaway(monkeypatch):
    monkeypatch.setattr(
        scriptwriter,
        "rewrite_script_draft",
        lambda *a, **k: json.dumps(
            {
                "statements": [
                    {
                        "id": 1,
                        "claim": "Новость объявлена.",
                        "status": "supported",
                        "evidence_ids": ["S1"],
                        "reason": "S1, " * 1000,
                    }
                ],
            }
        ),
    )
    with pytest.raises(ValueError, match="protocol limit"):
        scene_editor.audit_scene("mark: Новость объявлена.", "Новость объявлена.", model="local")


def test_audit_does_not_accept_repeated_source_ids_as_additional_evidence(monkeypatch):
    monkeypatch.setattr(
        scriptwriter,
        "rewrite_script_draft",
        lambda *a, **k: json.dumps(
            {
                "statements": [
                    {
                        "id": 1,
                        "claim": "Новость объявлена.",
                        "status": "supported",
                        "evidence_ids": ["S1", "S1"],
                        "reason": "",
                    }
                ],
            }
        ),
    )
    with pytest.raises(ValueError, match="repeats"):
        scene_editor.audit_scene("mark: Новость объявлена.", "Новость объявлена.", model="local")


def test_fact_audit_cannot_omit_a_statement(monkeypatch):
    monkeypatch.setattr(
        scriptwriter,
        "rewrite_script_draft",
        lambda *a, **k: json.dumps(
            {
                "statements": [
                    {"id": 1, "status": "supported", "evidence_ids": ["S1"], "reason": ""}
                ],
            }
        ),
    )
    with pytest.raises(ValueError, match="every script statement"):
        scene_editor.audit_scene(
            "mark: Первая мысль. Вторая мысль.", "Первая мысль. Вторая мысль.", model="local"
        )


def test_audit_batches_preserve_all_statements_and_complete_source(monkeypatch):
    checked = []
    monkeypatch.setattr(scene_editor.settings, "llm_factcheck_batch_size", 2)
    source = "Полный источник. Существенная оговорка в конце."

    def generate(payload, **kwargs):
        data = json.loads(payload)
        assert " ".join(data["source_evidence"].values()) == source
        assert len(data["script_statements"]) <= 2
        checked.extend(item["text"] for item in data["script_statements"])
        return json.dumps(
            {
                "statements": [
                    {
                        "id": item["id"],
                        "claim": item["text"],
                        "status": "unsupported",
                        "evidence_ids": [],
                        "reason": "Проверено",
                    }
                    for item in data["script_statements"]
                ]
            }
        )

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    sentences = [f"Утверждение номер {index}." for index in range(30)]
    result = scene_editor.audit_scene("mark: " + " ".join(sentences), source, model="local")
    assert checked == sentences
    assert len(result["unsupported_claims"]) == 30


def test_fact_audit_schema_and_context_prefix_are_identical_across_batches(monkeypatch):
    monkeypatch.setattr(scene_editor.settings, "llm_factcheck_batch_size", 5)
    source = "Полный источник. Оговорка в самом конце."
    script = "mark: " + " ".join(f"Утверждение {index}." for index in range(6))
    formats, prefixes, checked = [], [], []

    def generate(payload, **kwargs):
        data = json.loads(payload)
        assert data["dialogue_context"] == script
        assert " ".join(data["source_evidence"].values()) == source
        formats.append(json.dumps(kwargs["response_format"], ensure_ascii=False))
        prefixes.append(payload.partition('"script_statements":')[0])
        items = kwargs["response_format"]["json_schema"]["schema"]["properties"]["statements"]
        assert items["minItems"] == 1 and items["maxItems"] == 5
        props = items["items"]["properties"]
        assert props["id"] == {"type": "integer", "minimum": 1}
        assert props["reason"]["maxLength"] == 480
        checked.extend(item["id"] for item in data["script_statements"])
        return json.dumps(
            {
                "statements": [
                    {
                        "id": item["id"],
                        "claim": item["text"],
                        "reason": "Проверено.",
                        "evidence_ids": [],
                        "status": "unsupported",
                    }
                    for item in data["script_statements"]
                ]
            }
        )

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    scene_editor.audit_scene(script, source, model="local")
    assert len(formats) == 2 and formats[0] == formats[1]
    assert prefixes[0] == prefixes[1] and checked == [1, 2, 3, 4, 5, 6]


@pytest.mark.parametrize("identities", [[1], [1, 3], [1, 2, 2]])
def test_fixed_audit_schema_retains_exact_runtime_id_checks(monkeypatch, identities):
    def generate(payload, **kwargs):
        by_id = {item["id"]: item["text"] for item in json.loads(payload)["script_statements"]}
        return json.dumps(
            {
                "statements": [
                    {
                        "id": identity,
                        "claim": by_id.get(identity, "Чужое утверждение."),
                        "reason": "",
                        "evidence_ids": ["S1"],
                        "status": "supported",
                    }
                    for identity in identities
                ]
            }
        )

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    with pytest.raises(ValueError, match="every script statement|repeated turn ID"):
        scene_editor.audit_scene(
            "mark: Первая мысль. Вторая мысль.", "Полный источник.", model="local"
        )


def test_audit_keeps_dialogue_scope_across_statement_batches(monkeypatch):
    monkeypatch.setattr(scene_editor.settings, "llm_factcheck_batch_size", 1)
    script = "nika: Поддерживаются две платформы.\nartem: Это устанавливается через отладочный интерфейс."
    calls = []

    def generate(payload, **kwargs):
        data = json.loads(payload)
        assert data["dialogue_context"] == script
        assert len(data["script_statements"]) == 1
        item = data["script_statements"][0]
        calls.append(item["id"])
        return json.dumps(
            {
                "statements": [
                    {
                        "id": item["id"],
                        "claim": item["text"],
                        "status": "unsupported",
                        "evidence_ids": [],
                        "reason": "Область действия требует уточнения",
                    },
                ]
            }
        )

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    scene_editor.audit_scene(
        script, "Только первый вариант использует отладочный интерфейс.", model="local"
    )
    assert calls == [1, 2]


def test_audit_preflights_complete_context_before_calling_model(monkeypatch):
    monkeypatch.setattr(scriptwriter.settings, "ollama_context_length", 4000)

    def generate(*args, **kwargs):
        pytest.fail("An oversized complete source must fail before a request.")

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    with pytest.raises(ValueError, match="complete source exceeds"):
        scene_editor.audit_scene("nika: Запуск завтра.", "Полный источник " * 5000, model="local")


@pytest.mark.parametrize("weight", [None, True, 0, -1, "2", float("nan"), float("inf")])
def test_plan_rejects_invalid_depth_weights(monkeypatch, weight):
    scene = {
        "index": 1,
        "direction": "Открытый вопрос",
        "participants": ["mark", "nika"],
        "depth_weight": weight,
    }
    monkeypatch.setattr(
        scriptwriter, "rewrite_script_draft", lambda *a, **k: json.dumps({"scenes": [scene]})
    )
    with pytest.raises(ValueError, match="finite positive"):
        scene_editor.plan_scenes(["Полная новость"], model="local")


def test_fact_audit_uses_distinct_source_ids_and_bounded_output_schema(monkeypatch):
    def generate(payload, **kwargs):
        data = json.loads(payload)
        assert list(data["source_evidence"]) == ["S1", "S2"]
        items = kwargs["response_format"]["json_schema"]["schema"]["properties"]["statements"]
        assert items["minItems"] == 1
        assert items["maxItems"] == scene_editor.settings.llm_factcheck_batch_size
        props = items["items"]["properties"]
        assert list(props).index("reason") < list(props).index("status")
        return json.dumps(
            {
                "statements": [
                    {
                        "id": item["id"],
                        "claim": item["text"],
                        "reason": "",
                        "evidence_ids": ["S1"],
                        "status": "supported",
                    }
                    for item in data["script_statements"]
                ]
            }
        )

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    scene_editor.audit_scene("mark: Факт.", "Факт. Оговорка.", model="local")


def test_evidence_schema_does_not_repeat_the_source_index_as_a_completion_example(monkeypatch):
    formats = []

    def generate(payload, **kwargs):
        formats.append(kwargs["response_format"])
        return json.dumps(
            {
                "statements": [
                    {
                        "id": 1,
                        "claim": "Полная новость.",
                        "reason": "",
                        "evidence_ids": ["S1"],
                        "status": "supported",
                    },
                ]
            }
        )

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    scene_editor.audit_scene("mark: Полная новость.", "Полная новость.", model="local")
    scene_editor.audit_scene("mark: Полная новость.", "Полная новость.\n" * 100, model="local")
    assert formats[0] == formats[1]


def test_fact_audit_cannot_attach_a_verdict_to_a_different_statement(monkeypatch):
    monkeypatch.setattr(
        scriptwriter,
        "rewrite_script_draft",
        lambda *a, **k: json.dumps(
            {
                "statements": [
                    {
                        "id": 1,
                        "claim": "Другое утверждение.",
                        "reason": "",
                        "evidence_ids": ["S1"],
                        "status": "supported",
                    }
                ],
            }
        ),
    )
    with pytest.raises(ValueError, match="different statement"):
        scene_editor.audit_scene(
            "mark: Исходное утверждение.", "Исходное утверждение.", model="local"
        )


def test_discussion_does_not_require_news_evidence_but_source_facts_still_do(monkeypatch):
    def generate(payload, **kwargs):
        claims = json.loads(payload)["script_statements"]
        return json.dumps(
            {
                "statements": [
                    {
                        "id": claims[0]["id"],
                        "claim": claims[0]["text"],
                        "reason": "",
                        "evidence_ids": ["S1"],
                        "status": "supported",
                    },
                    {
                        "id": claims[1]["id"],
                        "claim": claims[1]["text"],
                        "reason": "Явное мнение",
                        "evidence_ids": [],
                        "status": "discussion",
                    },
                ]
            }
        )

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    result = scene_editor.audit_scene(
        "mark: Доступ открыт.\nnika: На мой взгляд, идея интересная.",
        "Доступ открыт.",
        model="local",
    )
    assert len(result["supported_claims"]) == 1
    assert not result["unsupported_claims"]
