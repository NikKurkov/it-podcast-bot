from types import SimpleNamespace

import pytest

from app.llm import news_ranker
from app.pipeline.scoring import RankedPost


def candidate(post_id):
    return RankedPost(
        post=SimpleNamespace(
            id=post_id,
            text=f"Исходная новость {post_id}",
            source_channel=SimpleNamespace(username="source"),
        ),
        score=10,
        reasons=[],
        penalties=[],
        topics=["ai"],
    )


def test_editorial_selection_accepts_only_input_ids_and_preserves_ranked_data(monkeypatch):
    monkeypatch.setattr(
        news_ranker,
        "rewrite_script_draft",
        lambda *a, **k: '{"selected":[{"id":2,"reason":"Новая функция безопасности"}]}',
    )
    selected = news_ranker.select_editorial_posts([candidate(1), candidate(2)], limit=1)
    assert [item.post.id for item in selected] == [2]
    assert "Новая функция безопасности" in selected[0].reasons[0]
    assert selected[0].post.text == "Исходная новость 2"


@pytest.mark.parametrize(
    "response",
    [
        '{"selected":[{"id":999,"reason":"fabricated"}]}',
        '{"selected":[{"id":1,"reason":"a"},{"id":1,"reason":"b"}]}',
        '{"selected":[{"id":true,"reason":"wrong type"}]}',
        "not json",
    ],
)
def test_editorial_selection_rejects_invalid_model_output(monkeypatch, response):
    monkeypatch.setattr(news_ranker, "rewrite_script_draft", lambda *a, **k: response)
    with pytest.raises(ValueError):
        news_ranker.select_editorial_posts([candidate(1)], limit=2)


def test_editorial_batches_limit_attention_without_dropping_source_text(monkeypatch):
    import json

    monkeypatch.setattr(news_ranker.settings, "llm_editorial_batch_size", 2)
    monkeypatch.setattr(news_ranker.settings, "ollama_context_length", 100000)
    originals = []

    def generate(payload, **kwargs):
        rows = json.loads(payload[payload.index("[") :])
        if rows and "text" in rows[0]:
            assert len(rows) <= 2
            originals.extend(row["text"] for row in rows)
        return json.dumps(
            {
                "selected": [
                    {
                        "id": rows[0]["id"],
                        "reason": rows[0].get("text", rows[0].get("editorial_brief")),
                    }
                ]
            }
        )

    monkeypatch.setattr(news_ranker, "rewrite_script_draft", generate)
    items = [candidate(index) for index in range(1, 6)]
    for item in items:
        item.post.text += ". Last caveat."
    news_ranker.select_editorial_posts(items, limit=2, model="local")
    assert set(originals) == {item.post.text for item in items}


def test_final_review_rechecks_original_source_not_a_hallucinated_brief(monkeypatch):
    import json

    item = candidate(1)
    item.post.text = "Продукт существует давно. Новая версия не была объявлена."
    phases = []

    def generate(payload, **kwargs):
        if "заключительная проверка" in kwargs["system_prompt"]:
            phases.append("verify")
            assert item.post.text in payload
            assert "Запуск сегодня" not in payload
            return '{"selected": []}'
        phases.append("select")
        return json.dumps({"selected": [{"id": 1, "reason": "Запуск сегодня"}]})

    monkeypatch.setattr(news_ranker, "rewrite_script_draft", generate)
    assert news_ranker.select_editorial_posts([item], limit=1, model="local") == []
    assert phases == ["select", "verify"]


def test_rejected_early_favorite_does_not_hide_later_good_candidates(monkeypatch):
    monkeypatch.setattr(news_ranker.settings, "llm_editorial_batch_size", 1)
    ranked = []

    def choose(items, **kwargs):
        for item in items:
            if not item.reasons:
                item.reasons.append("Complete editorial brief")
        if "заключительная проверка" in kwargs["prompt"]:
            return [item for item in items if item.post.id != 1]
        if "editorial_brief" in kwargs["payload"]:
            ranked.extend(item.post.id for item in items)
            return [item for item in items if item.post.id == 3]
        return items

    monkeypatch.setattr(news_ranker, "_choose", choose)
    selected = news_ranker.select_editorial_posts(
        [candidate(1), candidate(2), candidate(3)], limit=1, model="local"
    )
    assert ranked == [2, 3]
    assert [item.post.id for item in selected] == [3]
