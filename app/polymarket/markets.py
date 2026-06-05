"""Fetch, normalize, and filter crypto markets from the Gamma API."""
from app.polymarket.gamma_client import GammaClient


def normalize_market(m: dict) -> dict:
    """Extract the fields we care about from a raw Gamma API market."""
    try:
        outcome_prices = eval(m.get("outcomePrices", "[null, null]"))
        yes_price = float(outcome_prices[0]) if outcome_prices[0] else None
        no_price = float(outcome_prices[1]) if outcome_prices[1] else None
    except Exception:
        yes_price = no_price = None

    return {
        "id": m.get("id"),
        "question": m.get("question", ""),
        "description": m.get("description", ""),
        "resolution_source": m.get("resolutionSource", ""),
        "end_date": m.get("endDateIso") or m.get("endDate", ""),
        "yes_price": yes_price,
        "no_price": no_price,
        "best_bid": float(m["bestBid"]) if m.get("bestBid") else None,
        "best_ask": float(m["bestAsk"]) if m.get("bestAsk") else None,
        "spread": float(m["spread"]) if m.get("spread") else None,
        "last_trade_price": float(m["lastTradePrice"]) if m.get("lastTradePrice") else None,
        "liquidity": float(m.get("liquidityNum") or m.get("liquidity") or 0),
        "volume": float(m.get("volume") or 0),
        "volume_24hr": float(m.get("volume24hr") or 0),
        "active": m.get("active", False),
        "accepting_orders": m.get("acceptingOrders", False),
        "clob_token_ids": m.get("clobTokenIds", []),
        "slug": m.get("slug", ""),
    }


def fetch_crypto_markets(limit: int = 200) -> list[dict]:
    """Return normalized active crypto markets using the Gamma events category filter."""
    client = GammaClient()
    try:
        events = client.get_events(limit=limit, category="Crypto")
        markets = []
        for event in events:
            for m in event.get("markets", []):
                if m.get("active") and not m.get("closed"):
                    markets.append(normalize_market(m))
        return markets
    finally:
        client.close()
