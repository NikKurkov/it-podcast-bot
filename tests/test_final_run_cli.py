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
            "--no-publish",
        ],
    )

    args = final_run.parse_args()

    assert args.collect_limit == 10
    assert args.pool_limit == 20
    assert args.top == 3
    assert args.publish is False


def test_auto_select_posts_excludes_previous_episode_posts(monkeypatch) -> None:
    post_a = _Post(1, "fresh")
    post_b = _Post(2, "previous")
    selected_ids = []

    monkeypatch.setattr(final_run, "get_posts_for_digest", lambda *args, **kwargs: [post_a, post_b])
    monkeypatch.setattr(final_run, "get_recent_db_episode_post_ids", lambda session, limit=1: set())
    monkeypatch.setattr(final_run, "get_recent_episode_post_ids", lambda limit=1: {2})
    monkeypatch.setattr(final_run, "load_source_weights", lambda: {})
    monkeypatch.setattr(final_run, "load_exclude_keywords", lambda: [])
    monkeypatch.setattr(final_run, "contains_excluded_keyword", lambda text, keywords: False)
    monkeypatch.setattr(
        final_run,
        "rank_posts",
        lambda posts, source_weights=None: [_RankedPost(post) for post in posts],
    )
    monkeypatch.setattr(final_run, "diversify_ranked_posts", lambda ranked_posts, limit: ranked_posts[:limit])

    def fake_update_editorial_state(session, post_ids, **kwargs):
        if kwargs.get("selected") is True:
            selected_ids.extend(post_ids)
        return len(post_ids)

    monkeypatch.setattr(final_run, "update_editorial_state", fake_update_editorial_state)

    assert final_run._auto_select_posts(object(), pool_limit=10, top=5) == 1
    assert selected_ids == [1]


def test_auto_select_posts_prefers_db_episode_history(monkeypatch) -> None:
    post_a = _Post(1, "fresh")
    post_b = _Post(2, "previous")
    selected_ids = []

    monkeypatch.setattr(final_run, "get_posts_for_digest", lambda *args, **kwargs: [post_a, post_b])
    monkeypatch.setattr(final_run, "get_recent_db_episode_post_ids", lambda session, limit=1: {2})
    monkeypatch.setattr(final_run, "get_recent_episode_post_ids", lambda limit=1: set())
    monkeypatch.setattr(final_run, "load_source_weights", lambda: {})
    monkeypatch.setattr(final_run, "load_exclude_keywords", lambda: [])
    monkeypatch.setattr(final_run, "contains_excluded_keyword", lambda text, keywords: False)
    monkeypatch.setattr(
        final_run,
        "rank_posts",
        lambda posts, source_weights=None: [_RankedPost(post) for post in posts],
    )
    monkeypatch.setattr(final_run, "diversify_ranked_posts", lambda ranked_posts, limit: ranked_posts[:limit])

    def fake_update_editorial_state(session, post_ids, **kwargs):
        if kwargs.get("selected") is True:
            selected_ids.extend(post_ids)
        return len(post_ids)

    monkeypatch.setattr(final_run, "update_editorial_state", fake_update_editorial_state)

    assert final_run._auto_select_posts(object(), pool_limit=10, top=5) == 1
    assert selected_ids == [1]


class _Post:
    def __init__(self, post_id: int, text: str) -> None:
        self.id = post_id
        self.text = text


class _RankedPost:
    score = 1.0
    reasons = ["test"]
    topics = []
    penalties = []

    def __init__(self, post: _Post) -> None:
        self.post = post
