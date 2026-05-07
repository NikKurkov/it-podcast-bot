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


@dataclass(frozen=True)
class PostScoreBreakdown:
    total: float
    engagement: float
    freshness: float
    length: float
    it_relevance: float
    investigation_potential: float
    penalty: float
    reasons: list[str]
    penalties: list[str]


IT_KEYWORDS = {
    "ai",
    "api",
    "backend",
    "cve",
    "devops",
    "docker",
    "frontend",
    "github",
    "gpu",
    "kubernetes",
    "linux",
    "llm",
    "open source",
    "python",
    "sql",
    "архитектур",
    "безопасност",
    "бэкенд",
    "веб",
    "данн",
    "зависимост",
    "инфраструктур",
    "искусственн",
    "код",
    "модел",
    "нейросет",
    "обновлен",
    "продакшен",
    "разработ",
    "релиз",
    "сервер",
    "уязвимост",
    "фронтенд",
}

INVESTIGATION_KEYWORDS = {
    "атака",
    "безопасност",
    "взлом",
    "доступ",
    "инцидент",
    "контроль",
    "откат",
    "ошибк",
    "падал",
    "причин",
    "продакшен",
    "production",
    "rollback",
    "risk",
    "security",
    "supply chain",
    "уязвимост",
    "цепочк",
}

LOW_SIGNAL_KEYWORDS = {
    "больше никогда",
    "жми",
    "забираем",
    "идеально",
    "переходим",
    "подпис",
    "скидк",
    "сохраняем",
    "срочно",
    "тут",
    "успей",
    "аниме",
    "мозг",
    "отношени",
    "премьер",
    "секс",
    "трейлер",
    "чипс",
    "шибари",
}


def rank_posts(posts: list[TelegramPost], now: datetime | None = None) -> list[RankedPost]:
    reference_time = now or datetime.now(timezone.utc)
    ranked_posts = [
        _rank_post(post, now=reference_time)
        for post in posts
    ]
    return sorted(
        ranked_posts,
        key=lambda ranked_post: (ranked_post.score, ranked_post.post.message_date),
        reverse=True,
    )


def score_post(post: TelegramPost, now: datetime | None = None) -> float:
    return score_post_breakdown(post, now=now).total


def score_post_breakdown(post: TelegramPost, now: datetime | None = None) -> PostScoreBreakdown:
    reference_time = now or datetime.now(timezone.utc)
    engagement_score = _engagement_score(post)
    freshness_score = _freshness_score(post.message_date, reference_time)
    length_score = _length_score(post.text)
    relevance_score, relevance_reasons = _keyword_score(post.text, IT_KEYWORDS, max_score=3.0)
    investigation_score, investigation_reasons = _keyword_score(
        post.text,
        INVESTIGATION_KEYWORDS,
        max_score=2.0,
    )
    penalty_score, penalties = _penalty_score(
        post.text,
        relevance_score=relevance_score,
        investigation_score=investigation_score,
    )
    total = round(
        engagement_score
        + freshness_score
        + length_score
        + relevance_score
        + investigation_score
        - penalty_score,
        4,
    )
    reasons = []
    if engagement_score >= 4:
        reasons.append("strong engagement")
    if freshness_score >= 2:
        reasons.append("fresh")
    reasons.extend(relevance_reasons)
    reasons.extend(investigation_reasons)

    return PostScoreBreakdown(
        total=total,
        engagement=round(engagement_score, 4),
        freshness=round(freshness_score, 4),
        length=round(length_score, 4),
        it_relevance=round(relevance_score, 4),
        investigation_potential=round(investigation_score, 4),
        penalty=round(penalty_score, 4),
        reasons=_deduplicate(reasons),
        penalties=_deduplicate(penalties),
    )


def _rank_post(post: TelegramPost, now: datetime) -> RankedPost:
    breakdown = score_post_breakdown(post, now=now)
    return RankedPost(
        post=post,
        score=breakdown.total,
        reasons=breakdown.reasons,
        penalties=breakdown.penalties,
    )


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


def _length_score(text: str) -> float:
    length = len(text)
    if 120 <= length <= 1200:
        return 1.0
    if 60 <= length < 120 or 1200 < length <= 1800:
        return 0.5
    return 0.0


def _keyword_score(text: str, keywords: set[str], max_score: float) -> tuple[float, list[str]]:
    normalized_text = text.casefold()
    matched_keywords = [keyword for keyword in keywords if keyword in normalized_text]
    if not matched_keywords:
        return 0.0, []

    score = min(max_score, 0.65 * len(matched_keywords))
    top_keywords = sorted(matched_keywords)[:4]
    return score, [f"keywords: {', '.join(top_keywords)}"]


def _penalty_score(
    text: str,
    relevance_score: float,
    investigation_score: float,
) -> tuple[float, list[str]]:
    normalized_text = text.casefold()
    matched_keywords = [keyword for keyword in LOW_SIGNAL_KEYWORDS if keyword in normalized_text]
    penalties = []
    penalty = 0.0
    if matched_keywords:
        penalty += min(2.5, 0.7 * len(matched_keywords))
        penalties.append(f"low-signal wording: {', '.join(sorted(matched_keywords)[:4])}")

    emoji_count = sum(1 for char in text if ord(char) > 10_000)
    if emoji_count >= 6:
        penalty += 0.8
        penalties.append("many emoji")

    if relevance_score == 0 and investigation_score == 0:
        penalty += 4.0
        penalties.append("no IT or investigation signals")

    return penalty, penalties


def _deduplicate(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
