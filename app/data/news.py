"""News ingestion: CoinDesk RSS (primary), Decrypt RSS (secondary), Fear & Greed Index."""
import feedparser
import httpx
import structlog
from datetime import datetime, timezone

log = structlog.get_logger()

RSS_FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", 0.9),
    ("Decrypt", "https://decrypt.co/feed", 0.8),
    ("CoinTelegraph", "https://cointelegraph.com/rss", 0.85),
]

CRYPTO_KEYWORDS = [
    "bitcoin", "btc", "ethereum", "eth", "crypto", "blockchain",
    "defi", "solana", "sol", "etf", "sec", "regulation", "fed",
    "interest rate", "inflation", "stablecoin", "altcoin",
]


def fetch_news(limit: int = 30) -> list[dict]:
    """Fetch and normalize recent crypto news from RSS feeds."""
    all_items = []
    for source_name, url, credibility in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:limit // len(RSS_FEEDS) + 5]:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                published = entry.get("published", "")
                link = entry.get("link", "")
                if _is_relevant(title + " " + summary):
                    all_items.append({
                        "title": title,
                        "summary": summary[:500],
                        "source": source_name,
                        "source_credibility_score": credibility,
                        "url": link,
                        "published": published,
                        "sentiment_score": None,  # filled by AI layer
                        "relevance_score": None,
                    })
            log.debug("news_fetched", source=source_name, count=len(feed.entries))
        except Exception as e:
            log.warning("news_feed_failed", source=source_name, error=str(e))

    return all_items[:limit]


def _is_relevant(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in CRYPTO_KEYWORDS)


def get_fear_greed() -> dict:
    """Fetch the Crypto Fear & Greed Index (0=extreme fear, 100=extreme greed)."""
    try:
        r = httpx.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        r.raise_for_status()
        item = r.json()["data"][0]
        value = int(item["value"])
        # Normalize to -1.0 (extreme fear) to +1.0 (extreme greed)
        normalized = (value - 50) / 50.0
        return {
            "value": value,
            "classification": item["value_classification"],
            "normalized": round(normalized, 3),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.warning("fear_greed_failed", error=str(e))
        return {"value": 50, "classification": "Neutral", "normalized": 0.0, "timestamp": None}
