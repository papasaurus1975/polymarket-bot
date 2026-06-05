"""Fetch, normalize, and store markets from Gamma API."""
from app.polymarket.gamma_client import GammaClient

CRYPTO_KEYWORDS = [
    "bitcoin", "btc", "ethereum", "eth", "solana", "sol", "xrp",
    "dogecoin", "doge", "crypto", "stablecoin", "etf", "defi",
    "tvl", "token", "blockchain", "on-chain", "funding rate",
]


def is_crypto_market(market: dict) -> bool:
    text = (market.get("question", "") + " " + market.get("description", "")).lower()
    return any(kw in text for kw in CRYPTO_KEYWORDS)


def fetch_crypto_markets(limit: int = 200) -> list[dict]:
    """Return active Polymarket markets that are crypto-related."""
    client = GammaClient()
    try:
        markets = client.get_markets(limit=limit)
        return [m for m in markets if is_crypto_market(m)]
    finally:
        client.close()
