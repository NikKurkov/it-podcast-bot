import re
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
    length: float
    it_relevance: float
    investigation_potential: float
    source_weight: float
    penalty: float
    topics: list[str]
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

CONSUMER_TOPIC_KEYWORDS = {
    "авто",
    "автомобил",
    "болид",
    "игр",
    "кроссов",
    "планшет",
    "смартфон",
    "сабо",
    "тапк",
    "фильм",
    "формул",
    "crocs",
    "li auto",
    "subnautica",
    "xperia",
}

TOPIC_KEYWORDS = {
    "ai": {
        "ai",
        "gpt",
        "llm",
        "claude",
        "gemma",
        "модел",
        "нейросет",
        "искусственн",
        "агент",
        "промпт",
    },
    "security": {
        "cve",
        "security",
        "supply chain",
        "атака",
        "безопасност",
        "взлом",
        "инцидент",
        "уязвимост",
        "цепочк",
    },
    "devops": {
        "ci",
        "devops",
        "docker",
        "kubernetes",
        "linux",
        "observability",
        "инфраструктур",
        "наблюдаем",
        "продакшен",
        "сервер",
    },
    "tools": {
        "api",
        "github",
        "obs",
        "tool",
        "инструмент",
        "код",
        "монтаж",
        "таблиц",
    },
    "frontend": {
        "css",
        "frontend",
        "react",
        "ui",
        "ux",
        "веб",
        "интерфейс",
        "фронтенд",
    },
}


def rank_posts(
    posts: list[TelegramPost],
    now: datetime | None = None,
    source_weights: dict[str, float] | None = None,
) -> list[RankedPost]:
    reference_time = now or datetime.now(timezone.utc)
    ranked_posts = [
        _rank_post(post, now=reference_time, source_weights=source_weights or {})
        for post in posts
    ]
    return sorted(
        ranked_posts,
        key=lambda ranked_post: (ranked_post.score, ranked_post.post.message_date),
        reverse=True,
    )


def diversify_ranked_posts(
    ranked_posts: list[RankedPost],
    limit: int,
    max_per_source: int = 2,
    max_per_topic: int = 3,
    similarity_threshold: float = 0.42,
) -> list[RankedPost]:
    selected: list[RankedPost] = []
    source_counts: dict[str, int] = {}
    topic_counts: dict[str, int] = {}

    for ranked_post in ranked_posts:
        if len(selected) >= limit:
            break
        source = getattr(getattr(ranked_post.post, "source_channel", None), "username", "") or ""
        source_key = source.casefold()
        if source_key and source_counts.get(source_key, 0) >= max_per_source:
            continue
        if _is_topic_saturated(ranked_post.topics, topic_counts, max_per_topic):
            continue
        if _is_too_similar_to_selected(ranked_post, selected, similarity_threshold):
            continue

        selected.append(ranked_post)
        if source_key:
            source_counts[source_key] = source_counts.get(source_key, 0) + 1
        for topic in ranked_post.topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

    if len(selected) >= limit:
        return selected

    selected_ids = {ranked_post.post.id for ranked_post in selected}
    for ranked_post in ranked_posts:
        if len(selected) >= limit:
            break
        if ranked_post.post.id in selected_ids:
            continue
        if _is_too_similar_to_selected(ranked_post, selected, similarity_threshold):
            continue
        selected.append(ranked_post)
        selected_ids.add(ranked_post.post.id)

    return selected


def is_podcast_candidate(ranked_post: RankedPost, min_score: float = 1.0) -> bool:
    if ranked_post.score < min_score:
        return False
    if "no IT or investigation signals" in ranked_post.penalties:
        return False
    if any(penalty.startswith("consumer topic:") for penalty in ranked_post.penalties) and not ranked_post.topics:
        return False
    return True


def score_post(
    post: TelegramPost,
    now: datetime | None = None,
    source_weights: dict[str, float] | None = None,
) -> float:
    return score_post_breakdown(post, now=now, source_weights=source_weights).total


def score_post_breakdown(
    post: TelegramPost,
    now: datetime | None = None,
    source_weights: dict[str, float] | None = None,
) -> PostScoreBreakdown:
    reference_time = now or datetime.now(timezone.utc)
    source_weights = source_weights or {}
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
    source_weight = _source_weight_score(post, source_weights)
    topics = detect_topics(post.text)
    total = round(
        engagement_score
        + freshness_score
        + length_score
        + relevance_score
        + investigation_score
        + source_weight
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
    if topics:
        reasons.append(f"topics: {', '.join(topics)}")
    if source_weight > 0:
        reasons.append(f"source boost: +{source_weight:.2f}")
    elif source_weight < 0:
        penalties.append(f"source weight: {source_weight:.2f}")

    return PostScoreBreakdown(
        total=total,
        engagement=round(engagement_score, 4),
        freshness=round(freshness_score, 4),
        length=round(length_score, 4),
        it_relevance=round(relevance_score, 4),
        investigation_potential=round(investigation_score, 4),
        source_weight=round(source_weight, 4),
        penalty=round(penalty_score, 4),
        topics=topics,
        reasons=_deduplicate(reasons),
        penalties=_deduplicate(penalties),
    )


def _rank_post(
    post: TelegramPost,
    now: datetime,
    source_weights: dict[str, float],
) -> RankedPost:
    breakdown = score_post_breakdown(post, now=now, source_weights=source_weights)
    return RankedPost(
        post=post,
        score=breakdown.total,
        reasons=breakdown.reasons,
        penalties=breakdown.penalties,
        topics=breakdown.topics,
    )


def detect_topics(text: str) -> list[str]:
    topics = []
    normalized_text = text.casefold()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in normalized_text for keyword in keywords):
            topics.append(topic)
    return topics


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


def _source_weight_score(post: TelegramPost, source_weights: dict[str, float]) -> float:
    source_username = getattr(getattr(post, "source_channel", None), "username", None)
    if not source_username:
        return 0.0
    weight = source_weights.get(source_username.casefold(), 1.0)
    return max(-2.0, min(2.0, (weight - 1.0) * 4.0))


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
        penalty += 8.0
        penalties.append("no IT or investigation signals")

    consumer_keywords = [
        keyword for keyword in CONSUMER_TOPIC_KEYWORDS if keyword in normalized_text
    ]
    if consumer_keywords and relevance_score < 1.0 and investigation_score < 1.0:
        penalty += min(4.0, 1.2 * len(consumer_keywords))
        penalties.append(f"consumer topic: {', '.join(sorted(consumer_keywords)[:4])}")

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


def _is_topic_saturated(
    topics: list[str],
    topic_counts: dict[str, int],
    max_per_topic: int,
) -> bool:
    if not topics:
        return False
    return all(topic_counts.get(topic, 0) >= max_per_topic for topic in topics)


def _is_too_similar_to_selected(
    ranked_post: RankedPost,
    selected: list[RankedPost],
    similarity_threshold: float,
) -> bool:
    tokens = _content_tokens(ranked_post.post.text)
    if not tokens:
        return False
    signature = _topic_signature(ranked_post.post.text)

    for selected_post in selected:
        selected_tokens = _content_tokens(selected_post.post.text)
        if not selected_tokens:
            continue
        if signature and signature == _topic_signature(selected_post.post.text):
            return True
        if _has_same_named_event(tokens, selected_tokens):
            return True
        similarity = len(tokens & selected_tokens) / len(tokens | selected_tokens)
        if similarity >= similarity_threshold:
            return True
    return False


def _topic_signature(text: str) -> tuple[str, ...]:
    tokens = _content_tokens(_topic_lead(text))
    meaningful = [
        token
        for token in sorted(tokens)
        if not token.isdigit() and token not in TOPIC_SIGNATURE_STOP_WORDS
    ]
    return tuple(meaningful[:6])


def _topic_lead(text: str) -> str:
    normalized = " ".join(text.replace("\n", " ").split())
    match = re.search(r"\s+[—–-]\s+|[.:?!…]+(?:\s+|$)", normalized)
    if match:
        return normalized[: match.start()]
    return normalized[:160]


def _has_same_named_event(tokens: set[str], selected_tokens: set[str]) -> bool:
    shared = tokens & selected_tokens
    if len(shared & NAMED_EVENT_TOKENS) >= 1 and len(shared) >= 2:
        return True
    if len(shared & COMPANY_OR_PRODUCT_TOKENS) >= 1 and len(shared & EVENT_ACTION_TOKENS) >= 1:
        return True
    return False


def _content_tokens(text: str) -> set[str]:
    normalized = text.casefold().replace("ё", "е")
    tokens = set(re.findall(r"[a-zа-я0-9]{4,}", normalized))
    return tokens - CONTENT_STOP_WORDS


CONTENT_STOP_WORDS = {
    "https",
    "http",
    "www",
    "того",
    "если",
    "есть",
    "будет",
    "были",
    "также",
    "можно",
    "свои",
    "себя",
    "этот",
    "этой",
    "этом",
    "когда",
    "которые",
}

TOPIC_SIGNATURE_STOP_WORDS = CONTENT_STOP_WORDS | {
    "новост",
    "новость",
    "вышла",
    "вышел",
    "появил",
    "получил",
    "получит",
    "представ",
    "релиз",
    "сервис",
}

COMPANY_OR_PRODUCT_TOKENS = {
    "android",
    "apple",
    "chatgpt",
    "claude",
    "codex",
    "discord",
    "forza",
    "gemini",
    "github",
    "google",
    "instagram",
    "maigret",
    "memoir",
    "openai",
    "steam",
    "telegram",
    "windows",
    "андроид",
    "дискорд",
    "телеграм",
}

EVENT_ACTION_TOKENS = {
    "атака",
    "взлом",
    "доступност",
    "зависимость",
    "камер",
    "модел",
    "обновлен",
    "памят",
    "релиз",
    "сбой",
    "сбоит",
    "уязвимост",
}

NAMED_EVENT_TOKENS = COMPANY_OR_PRODUCT_TOKENS | {
    "rkn",
    "ooni",
    "ркн",
}
