from dataclasses import dataclass
from datetime import datetime, timezone
from math import log10

from app.db.models import TelegramPost


@dataclass(frozen=True)
class RankedPost:
    post: TelegramPost
    score: float


def rank_posts(posts: list[TelegramPost], now: datetime | None = None) -> list[RankedPost]:
    reference_time = now or datetime.now(timezone.utc)
    ranked_posts = [
        RankedPost(post=post, score=score_post(post, now=reference_time))
        for post in posts
    ]
    return sorted(
        ranked_posts,
        key=lambda ranked_post: (ranked_post.score, ranked_post.post.message_date),
        reverse=True,
    )


def score_post(post: TelegramPost, now: datetime | None = None) -> float:
    reference_time = now or datetime.now(timezone.utc)
    views_score = log10(max(post.views or 0, 1))
    forwards_score = log10(max(post.forwards or 0, 1)) * 2.0
    freshness_score = _freshness_score(post.message_date, reference_time)
    length_score = _length_score(post.text)
    return round(views_score + forwards_score + freshness_score + length_score, 4)


def _freshness_score(message_date: datetime, now: datetime) -> float:
    if message_date.tzinfo is None:
        message_date = message_date.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    age_hours = max((now - message_date).total_seconds() / 3600, 0)
    return max(0.0, 3.0 - age_hours / 12)


def _length_score(text: str) -> float:
    length = len(text)
    if 120 <= length <= 1200:
        return 1.0
    if 60 <= length < 120 or 1200 < length <= 1800:
        return 0.5
    return 0.0
