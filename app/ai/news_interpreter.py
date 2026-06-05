"""News summarization, relevance scoring, and sentiment analysis.

Rule-based scoring when AI is unavailable; OpenAI layer when configured.
"""
import re
import structlog
from app.ai.utils import ai_available

log = structlog.get_logger()

BULLISH_WORDS = [
    "approve", "approved", "adoption", "etf", "bull", "rally", "surge",
    "breakout", "ath", "all-time high", "buy", "accumulate", "partnership",
    "launch", "institutional", "mainstream", "upgrade",
]
BEARISH_WORDS = [
    "ban", "banned", "reject", "hack", "exploit", "crash", "sell-off",
    "bear", "regulatory", "lawsuit", "sec", "fraud", "collapse",
    "restrict", "crackdown", "fine", "warning",
]


def score_sentiment_rule_based(title: str, summary: str = "") -> float:
    """Return sentiment score -1.0 to +1.0 using keyword rules."""
    text = (title + " " + summary).lower()
    bull = sum(1 for w in BULLISH_WORDS if w in text)
    bear = sum(1 for w in BEARISH_WORDS if w in text)
    total = bull + bear
    if total == 0:
        return 0.0
    return round((bull - bear) / total, 3)


_SYNONYMS = {
    "btc": "bitcoin", "eth": "ethereum", "sol": "solana",
    "bitcoin": "btc", "ethereum": "eth", "solana": "sol",
}


def score_relevance(title: str, market_question: str) -> float:
    """Score how relevant a news item is to a specific market question (0.0–1.0)."""
    def expand(text: str) -> set[str]:
        words = set(re.findall(r'\b\w{3,}\b', text.lower()))
        return words | {_SYNONYMS[w] for w in words if w in _SYNONYMS}

    title_words = expand(title)
    question_words = expand(market_question)
    if not question_words:
        return 0.0
    overlap = len(title_words & question_words)
    return round(min(overlap / max(len(question_words), 1), 1.0), 3)


def enrich_news_with_sentiment(news_items: list[dict]) -> list[dict]:
    """Add sentiment_score to each news item. Uses OpenAI if available, else rule-based."""
    if ai_available():
        return _enrich_with_openai(news_items)
    log.debug("news_sentiment_rule_based", count=len(news_items))
    for item in news_items:
        item["sentiment_score"] = score_sentiment_rule_based(
            item.get("title", ""), item.get("summary", "")
        )
    return news_items


def score_news_relevance(news_item: dict, market: dict) -> float:
    return score_relevance(news_item.get("title", ""), market.get("question", ""))


def get_market_sentiment(news_items: list[dict], market_question: str,
                         min_relevance: float = 0.1) -> float:
    """
    Aggregate sentiment for a market question from relevant news items.
    Returns weighted average sentiment weighted by relevance × credibility.
    """
    weighted_sum = 0.0
    weight_total = 0.0
    for item in news_items:
        rel = score_relevance(item.get("title", ""), market_question)
        if rel < min_relevance:
            continue
        sentiment = item.get("sentiment_score")
        if sentiment is None:
            sentiment = score_sentiment_rule_based(item.get("title", ""), item.get("summary", ""))
        credibility = item.get("source_credibility_score", 0.5)
        weight = rel * credibility
        weighted_sum += sentiment * weight
        weight_total += weight

    if weight_total == 0:
        return 0.0
    return round(weighted_sum / weight_total, 4)


def _enrich_with_openai(news_items: list[dict]) -> list[dict]:
    """Use OpenAI to score sentiment for each news item."""
    try:
        from openai import OpenAI
        from app.config import settings
        client = OpenAI(api_key=settings.openai_api_key)

        titles = [item.get("title", "") for item in news_items]
        prompt = (
            "Score the sentiment of each crypto news headline from -1.0 (very bearish) "
            "to +1.0 (very bullish). Return ONLY a JSON array of floats in the same order.\n\n"
            + "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles))
        )
        resp = client.chat.completions.create(
            model="claude-haiku-4-5-20251001",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0,
        )
        import json
        scores = json.loads(resp.choices[0].message.content.strip())
        for item, score in zip(news_items, scores):
            item["sentiment_score"] = float(score)
        log.info("news_sentiment_ai", count=len(news_items))
    except Exception as e:
        log.warning("ai_sentiment_failed_fallback", error=str(e))
        for item in news_items:
            if item.get("sentiment_score") is None:
                item["sentiment_score"] = score_sentiment_rule_based(
                    item.get("title", ""), item.get("summary", "")
                )
    return news_items
