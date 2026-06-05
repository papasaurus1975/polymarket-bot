"""Resolution source parser and match scorer.

For each market, extracts the resolution source from the description field
and scores how well our data feeds match it (0.0 = no match, 1.0 = exact).
"""

KNOWN_SOURCES = ["coingecko", "binance", "coinmarketcap", "cmc", "coinbase", "deribit"]


def parse_resolution_source(description: str) -> dict:
    """Extract resolution_source, resolution_metric, and resolution_timestamp hint."""
    desc_lower = description.lower()
    source = next((s for s in KNOWN_SOURCES if s in desc_lower), "unknown")
    metric = "closing_price" if "closing price" in desc_lower else "last_trade" if "last trade" in desc_lower else "unknown"
    return {"resolution_source": source, "resolution_metric": metric}


def score_resolution_match(parsed: dict, available_feeds: list[str]) -> float:
    """Return 0.0–1.0 indicating how well our feeds match the resolution source."""
    src = parsed.get("resolution_source", "unknown")
    if src == "unknown":
        return 0.0
    if src in available_feeds:
        return 1.0
    # Correlated exchanges get partial credit
    correlated = {"coinbase": "binance", "binance": "coinbase"}
    if correlated.get(src) in available_feeds:
        return 0.4
    return 0.0
