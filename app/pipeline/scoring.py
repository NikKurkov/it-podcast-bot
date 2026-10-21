"""Content-neutral ordering and lexical duplicate detection.

Relevance and event identity are editorial judgments, delegated to the local
model. These metrics deliberately know nothing about products or subject areas.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from math import log10

from app.db.models import TelegramPost


@dataclass(frozen=True)
class RankedPost:
    post: TelegramPost
    score: float
    reasons: list[str]
    penalties: list[str]
    topics: list[str]


@dataclass(frozen=True)
class PostScoreBreakdown:
    total: float
    engagement: float
    freshness: float
    source_weight: float
    topics: list[str]
    reasons: list[str]
    penalties: list[str]


def rank_posts(posts, now=None, source_weights=None) -> list[RankedPost]:
    reference = now or datetime.now(timezone.utc)
    result = []
    for post in posts:
        score = score_post_breakdown(post, now=reference, source_weights=source_weights)
        result.append(RankedPost(post, score.total, score.reasons, score.penalties, score.topics))
    return sorted(result, key=lambda item: item.score, reverse=True)


def score_post(post, now=None, source_weights=None) -> float:
    return score_post_breakdown(post, now=now, source_weights=source_weights).total


def score_post_breakdown(post, now=None, source_weights=None) -> PostScoreBreakdown:
    engagement = _engagement_score(post)
    freshness = _freshness_score(post.message_date, now or datetime.now(timezone.utc))
    weight = _source_weight_score(post, source_weights or {})
    return PostScoreBreakdown(
        total=round(engagement + freshness + weight, 4),
        engagement=round(engagement, 4),
        freshness=round(freshness, 4),
        source_weight=weight,
        topics=[],
        reasons=["content-neutral engagement and freshness ordering"]
        + ([f"source boost: +{weight:.2f}"] if weight > 0 else []),
        penalties=[],
    )


def is_podcast_candidate(ranked_post: RankedPost) -> bool:
    """Only checks usable input; semantic eligibility requires the editor."""
    return bool(ranked_post.post.text.strip())


def diversify_ranked_posts(
    ranked_posts: list[RankedPost],
    limit: int,
) -> list[RankedPost]:
    # No source/topic quotas: retain editorial order and suppress exact copies.
    selected = []
    for item in ranked_posts:
        if len(selected) >= limit:
            break
        if not is_similar_to_any_text(item.post.text, [old.post.text for old in selected]):
            selected.append(item)
    return selected


def is_similar_to_any_text(text: str, previous_texts: list[str]) -> bool:
    # A small lexical difference can reverse the news. Only exact, whitespace-normalized
    # copies are safe to remove automatically; the editor decides semantic duplicates.
    normalized = " ".join(text.split())
    return bool(normalized) and any(normalized == " ".join(old.split()) for old in previous_texts)


def _engagement_score(post: TelegramPost) -> float:
    views_score = log10(max(post.views or 0, 1))
    forwards_score = log10(max(post.forwards or 0, 1)) * 1.7
    return views_score + forwards_score


def _freshness_score(message_date: datetime, now: datetime) -> float:
    if message_date.tzinfo is None:
        message_date = message_date.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    age_hours = max((now - message_date).total_seconds() / 3600, 0)
    return max(0.0, 3.0 - age_hours / 12)


def _source_weight_score(post: TelegramPost, source_weights: dict[str, float]) -> float:
    source_username = getattr(getattr(post, "source_channel", None), "username", None)
    if not source_username:
        return 0.0
    weight = source_weights.get(source_username.casefold(), 1.0)
    return max(-2.0, min(2.0, (weight - 1.0) * 4.0))
