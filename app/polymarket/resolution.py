"""Resolution source parser and match scorer.

Extracts the resolution source from the market's resolutionSource field
and scores how well our data feeds match it (0.0 = no match, 1.0 = exact).
"""

KNOWN_SOURCES = {
    "coingecko": ["coingecko"],
    "binance": ["binance"],
    "coinmarketcap": ["coinmarketcap", "cmc"],
    "coinbase": ["coinbase"],
    "deribit": ["deribit"],
    "official": ["official", "rockstar", "sec.gov", "federalreserve"],
}

AVAILABLE_FEEDS = ["binance", "coingecko", "coinbase"]


def parse_resolution_source(resolution_source: str, description: str = "") -> dict:
    """Extract resolution_source and resolution_metric from market fields."""
    text = (resolution_source + " " + description).lower()
    matched = "unknown"
    for canonical, aliases in KNOWN_SOURCES.items():
        if any(alias in text for alias in aliases):
            matched = canonical
            break

    metric = "unknown"
    if "closing price" in text or "close price" in text:
        metric = "closing_price"
    elif "last trade" in text or "last price" in text:
        metric = "last_trade"
    elif "24h average" in text or "24-hour average" in text:
        metric = "24h_average"

    return {"resolution_source": matched, "resolution_metric": metric}


def score_resolution_match(parsed: dict, available_feeds: list[str] = AVAILABLE_FEEDS) -> float:
    """Return 0.0–1.0 indicating how well our feeds match the resolution source."""
    src = parsed.get("resolution_source", "unknown")
    if src == "unknown":
        return 0.0
    if src in available_feeds:
        return 1.0
    correlated = {"coinbase": "binance", "binance": "coinbase"}
    if correlated.get(src) in available_feeds:
        return 0.4
    return 0.0
