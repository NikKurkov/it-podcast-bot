import sys

import scripts.final_run as final_run


def test_final_run_defaults_come_from_settings(monkeypatch) -> None:
    monkeypatch.setattr(final_run.settings, "final_collect_limit", 31)
    monkeypatch.setattr(final_run.settings, "final_pool_limit", 123)
    monkeypatch.setattr(final_run.settings, "final_top_posts", 7)
    monkeypatch.setattr(final_run.settings, "publish_telegram_on_final", True)
    monkeypatch.setattr(final_run.settings, "telegram_publish_channel_id", "-1001")
    monkeypatch.setattr(sys, "argv", ["final_run.py"])

    args = final_run.parse_args()

    assert args.collect_limit == 31
    assert args.pool_limit == 123
    assert args.top == 7
    assert args.history_limit == 5
    assert args.publish is True
    assert args.publish_channel_id == "-1001"


def test_final_run_cli_overrides_settings(monkeypatch) -> None:
    monkeypatch.setattr(final_run.settings, "final_collect_limit", 31)
    monkeypatch.setattr(final_run.settings, "final_pool_limit", 123)
    monkeypatch.setattr(final_run.settings, "final_top_posts", 7)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "final_run.py",
            "--collect-limit",
            "10",
            "--pool-limit",
            "20",
            "--top",
            "3",
            "--history-limit",
            "2",
            "--no-publish",
        ],
    )

    args = final_run.parse_args()

    assert args.collect_limit == 10
    assert args.pool_limit == 20
    assert args.top == 3
    assert args.history_limit == 2
    assert args.publish is False


def test_auto_select_posts_excludes_previous_episode_posts(monkeypatch) -> None:
    post_a = _Post(1, "fresh")
    post_b = _Post(2, "previous")
    selected_ids = []

    monkeypatch.setattr(final_run, "get_posts_for_digest", lambda *args, **kwargs: [post_a, post_b])
    monkeypatch.setattr(final_run, "get_recent_episode_post_texts", lambda limit=5: ["previous"])
    monkeypatch.setattr(final_run, "load_source_weights", lambda: {})
    monkeypatch.setattr(
        final_run,
        "rank_posts",
        lambda posts, source_weights=None: [_RankedPost(post) for post in posts],
    )
    monkeypatch.setattr(
        final_run, "diversify_ranked_posts", lambda ranked_posts, limit: ranked_posts[:limit]
    )

    def fake_update_editorial_state(session, post_ids, **kwargs):
        if kwargs.get("selected") is True:
            selected_ids.extend(post_ids)
        return len(post_ids)

    monkeypatch.setattr(final_run, "update_editorial_state", fake_update_editorial_state)

    assert final_run._auto_select_posts(object(), pool_limit=10, top=1) == 1
    assert selected_ids == [1]


def test_auto_select_posts_uses_published_text_snapshots(monkeypatch) -> None:
    post_a = _Post(1, "fresh")
    post_b = _Post(2, "previous")
    selected_ids = []

    monkeypatch.setattr(final_run, "get_posts_for_digest", lambda *args, **kwargs: [post_a, post_b])
    monkeypatch.setattr(final_run, "get_recent_episode_post_texts", lambda limit=5: ["previous"])
    monkeypatch.setattr(final_run, "load_source_weights", lambda: {})
    monkeypatch.setattr(
        final_run,
        "rank_posts",
        lambda posts, source_weights=None: [_RankedPost(post) for post in posts],
    )
    monkeypatch.setattr(
        final_run, "diversify_ranked_posts", lambda ranked_posts, limit: ranked_posts[:limit]
    )

    def fake_update_editorial_state(session, post_ids, **kwargs):
        if kwargs.get("selected") is True:
            selected_ids.extend(post_ids)
        return len(post_ids)

    monkeypatch.setattr(final_run, "update_editorial_state", fake_update_editorial_state)

    assert final_run._auto_select_posts(object(), pool_limit=10, top=1) == 1
    assert selected_ids == [1]


def test_auto_select_posts_filters_weak_podcast_candidates(monkeypatch) -> None:
    post_a = _Post(1, "strong")
    post_b = _Post(2, "weak")
    selected_ids = []

    monkeypatch.setattr(final_run, "get_posts_for_digest", lambda *args, **kwargs: [post_a, post_b])
    monkeypatch.setattr(final_run, "get_recent_episode_post_texts", lambda limit=5: [])
    monkeypatch.setattr(final_run, "load_source_weights", lambda: {})
    monkeypatch.setattr(
        final_run,
        "rank_posts",
        lambda posts, source_weights=None: [_RankedPost(post) for post in posts],
    )
    monkeypatch.setattr(
        final_run, "is_podcast_candidate", lambda ranked_post: ranked_post.post.id == 1
    )
    monkeypatch.setattr(
        final_run, "diversify_ranked_posts", lambda ranked_posts, limit: ranked_posts[:limit]
    )

    def fake_update_editorial_state(session, post_ids, **kwargs):
        if kwargs.get("selected") is True:
            selected_ids.extend(post_ids)
        return len(post_ids)

    monkeypatch.setattr(final_run, "update_editorial_state", fake_update_editorial_state)

    assert final_run._auto_select_posts(object(), pool_limit=10, top=1) == 1
    assert selected_ids == [1]


def test_auto_select_posts_excludes_recent_similar_episode_text(monkeypatch) -> None:
    post_a = _Post(1, "OpenAI выпустила новую модель для генерации речи")
    post_b = _Post(2, "GitHub стал хуже открываться в РФ, OONI пишет о снижении доступности")
    selected_ids = []

    monkeypatch.setattr(final_run, "get_posts_for_digest", lambda *args, **kwargs: [post_a, post_b])
    monkeypatch.setattr(
        final_run,
        "get_recent_episode_post_texts",
        lambda limit=5: [
            "РКН добрался до GitHub: OONI зафиксировал снижение доступности платформы в России.",
        ],
    )
    monkeypatch.setattr(final_run, "load_source_weights", lambda: {})
    monkeypatch.setattr(
        final_run,
        "rank_posts",
        lambda posts, source_weights=None: [_RankedPost(post) for post in posts],
    )
    monkeypatch.setattr(
        final_run, "diversify_ranked_posts", lambda ranked_posts, limit: ranked_posts[:limit]
    )

    def fake_update_editorial_state(session, post_ids, **kwargs):
        if kwargs.get("selected") is True:
            selected_ids.extend(post_ids)
        return len(post_ids)

    monkeypatch.setattr(final_run, "update_editorial_state", fake_update_editorial_state)

    assert final_run._auto_select_posts(object(), pool_limit=10, top=1, history_limit=5) == 1
    assert selected_ids == [1]


def test_auto_select_posts_keeps_history_when_fresh_selection_is_small(monkeypatch) -> None:
    post_a = _Post(1, "fresh")
    post_b = _Post(2, "previous")
    post_c = _Post(3, "also previous")
    selected_ids = []
    diagnostics = {}

    monkeypatch.setattr(
        final_run, "get_posts_for_digest", lambda *args, **kwargs: [post_a, post_b, post_c]
    )
    monkeypatch.setattr(
        final_run, "get_recent_episode_post_texts", lambda limit=5: ["previous", "also previous"]
    )
    monkeypatch.setattr(final_run, "load_source_weights", lambda: {})
    monkeypatch.setattr(
        final_run,
        "rank_posts",
        lambda posts, source_weights=None: [_RankedPost(post) for post in posts],
    )
    monkeypatch.setattr(
        final_run, "diversify_ranked_posts", lambda ranked_posts, limit: ranked_posts[:limit]
    )

    def fake_update_editorial_state(session, post_ids, **kwargs):
        if kwargs.get("selected") is True:
            selected_ids.extend(post_ids)
        return len(post_ids)

    monkeypatch.setattr(final_run, "update_editorial_state", fake_update_editorial_state)

    assert (
        final_run._auto_select_posts(
            object(),
            pool_limit=10,
            top=3,
            history_limit=5,
            diagnostics=diagnostics,
        )
        == 1
    )
    assert selected_ids == [1]
    assert diagnostics["selected_attempt"]["history_limit"] == 5


class _Post:
    def __init__(self, post_id: int, text: str) -> None:
        self.id = post_id
        self.text = text


class _RankedPost:
    score = 1.0
    reasons = ["test"]
    topics = ["tools"]
    penalties = []

    def __init__(self, post: _Post) -> None:
        self.post = post


def test_selection_requests_only_last_day_of_news(monkeypatch):
    from datetime import datetime, timedelta, timezone

    cutoffs = []

    def get_posts(*args, **kwargs):
        if kwargs.get("limit") != 10_000:
            cutoffs.append(kwargs.get("since"))
        return []

    monkeypatch.setattr(final_run, "get_posts_for_digest", get_posts)
    monkeypatch.setattr(final_run, "update_editorial_state", lambda *a, **k: 0)
    monkeypatch.setattr(final_run, "get_recent_episode_post_texts", lambda *a, **k: [])
    monkeypatch.setattr(final_run, "load_source_weights", lambda: {})
    before = datetime.now(timezone.utc) - timedelta(hours=24)
    final_run._auto_select_posts(object(), pool_limit=50, top=5)
    after = datetime.now(timezone.utc) - timedelta(hours=24)
    assert cutoffs and all(cutoff is not None and before <= cutoff <= after for cutoff in cutoffs)


def test_blocked_publication_returns_failure_status_without_generating(tmp_path, monkeypatch):
    from contextlib import nullcontext
    import json

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["final_run.py", "--no-collect", "--publish"])
    monkeypatch.setattr(final_run, "init_db", lambda: None)
    monkeypatch.setattr(final_run, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(final_run, "_auto_select_posts", lambda *a, **k: 0)

    def unexpected_package(*args, **kwargs):
        raise AssertionError("Must not generate audio without selected stories")

    monkeypatch.setattr(final_run, "create_episode_package", unexpected_package)
    assert final_run.main() == 2
    report = json.loads((tmp_path / "data/logs/latest_run_report.json").read_text())
    assert report["status"] == "blocked"


def test_failure_after_package_updates_latest_run_report(tmp_path, monkeypatch):
    import json
    import pytest
    from contextlib import nullcontext
    from tests.test_run_report import _package

    monkeypatch.chdir(tmp_path)
    package = _package(tmp_path / "episode")
    monkeypatch.setattr(sys, "argv", ["final_run.py", "--no-collect", "--publish"])
    monkeypatch.setattr(final_run, "init_db", lambda: None)
    monkeypatch.setattr(final_run, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(final_run, "_auto_select_posts", lambda *a, **k: 3)
    monkeypatch.setattr(final_run, "create_episode_package", lambda *a, **k: package)
    monkeypatch.setattr(final_run, "publication_gate_checks", lambda *a, **k: [])

    async def fail_publish(*args, **kwargs):
        raise RuntimeError("publish failed")

    monkeypatch.setattr(final_run, "publish_episode_package", fail_publish)
    with pytest.raises(RuntimeError, match="publish failed"):
        final_run.main()
    report = json.loads((package.path / "run_report.json").read_text())
    latest = json.loads((tmp_path / "data/logs/latest_run_report.json").read_text())
    assert report["status"] == latest["status"] == "failed"
    assert latest["package"] == str(package.path)


def test_same_id_edit_is_eligible_without_mutating_published_snapshot(tmp_path, monkeypatch):
    import json
    from datetime import datetime, timezone
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.db.models import Base
    from app.db.repositories.posts import save_or_update_post
    from app.db.repositories.sources import get_or_create_source
    from app.pipeline.episode_history import get_recent_episode_post_texts

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    path = tmp_path / "published"
    path.mkdir()
    (path / "telegram_publish.json").write_text(json.dumps({"message_id": 7}))
    original = "Новая версия доступна для установки."
    snapshot = json.dumps([{"post_id": 1, "text": original}], ensure_ascii=False)
    (path / "selected_posts.json").write_text(snapshot)
    monkeypatch.setattr(
        final_run,
        "get_recent_episode_post_texts",
        lambda **kwargs: get_recent_episode_post_texts(tmp_path, **kwargs),
    )
    monkeypatch.setattr(final_run, "load_source_weights", lambda: {})
    with Session(engine) as session:
        source = get_or_create_source(session, "updates")
        data = {
            "telegram_message_id": 42,
            "message_date": datetime.now(timezone.utc),
            "text": original,
        }
        before = save_or_update_post(session, source, data)["post"]
        kwargs = dict(pool_limit=10, top=5, history_limit=5, lookback_hours=24)
        assert final_run._build_selection(session, **kwargs)[0] == []
        after = save_or_update_post(
            session, source, {**data, "text": "Новая версия НЕ доступна для установки."}
        )["post"]
        assert after.id == before.id
        selected, _ = final_run._build_selection(session, **kwargs)
        assert [item.post.id for item in selected] == [before.id]
        assert (path / "selected_posts.json").read_text() == snapshot
