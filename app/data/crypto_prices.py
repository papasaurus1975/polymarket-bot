"""Crypto price feed with fallback chain: Coinbase → CoinGecko → HALT."""
import httpx
import structlog

log = structlog.get_logger()

COINGECKO_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
    "XRP": "ripple", "DOGE": "dogecoin", "BNB": "binancecoin",
    "ADA": "cardano", "AVAX": "avalanche-2", "DOT": "polkadot",
    "MATIC": "matic-network", "LINK": "chainlink", "UNI": "uniswap",
}


def get_price(symbol: str) -> float:
    """Return current USD price. Coinbase primary, CoinGecko fallback."""
    symbol = symbol.upper()
    for source, fetch in [("coinbase", _from_coinbase), ("coingecko", _from_coingecko)]:
        try:
            price = fetch(symbol)
            if price:
                log.debug("price_fetched", symbol=symbol, source=source, price=price)
                return price
        except Exception as e:
            log.warning("price_feed_failed", symbol=symbol, source=source, error=str(e))
    raise RuntimeError(f"All price feeds failed for {symbol}")


def get_historical_prices(symbol: str, days: int = 35) -> list[float]:
    """Return list of daily closing prices (oldest first). Used for volatility."""
    symbol = symbol.upper()
    slug = COINGECKO_IDS.get(symbol)
    if not slug:
        raise ValueError(f"No CoinGecko ID for {symbol}")
    resp = httpx.get(
        "https://api.coingecko.com/api/v3/coins/{}/market_chart".format(slug),
        params={"vs_currency": "usd", "days": days, "interval": "daily"},
        timeout=10,
    )
    resp.raise_for_status()
    return [p[1] for p in resp.json()["prices"]]


def _from_coinbase(symbol: str) -> float | None:
    resp = httpx.get(
        f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot", timeout=5
    )
    resp.raise_for_status()
    return float(resp.json()["data"]["amount"])


def _from_coingecko(symbol: str) -> float | None:
    slug = COINGECKO_IDS.get(symbol)
    if not slug:
        return None
    resp = httpx.get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={"ids": slug, "vs_currencies": "usd"},
        timeout=8,
    )
    resp.raise_for_status()
    return resp.json()[slug]["usd"]
