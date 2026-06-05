"""Crypto price feed with fallback chain: Binance → Coinbase → CoinGecko → HALT."""
import httpx


def get_price(symbol: str) -> float:
    """Return current USD price for symbol (e.g. 'BTC'). Raises on total failure."""
    for fetch in [_from_binance, _from_coingecko]:
        try:
            price = fetch(symbol)
            if price:
                return price
        except Exception:
            continue
    raise RuntimeError(f"All price feeds failed for {symbol}")


def _from_binance(symbol: str) -> float | None:
    resp = httpx.get(f"https://api.binance.com/api/v3/ticker/price", params={"symbol": f"{symbol}USDT"}, timeout=5)
    resp.raise_for_status()
    return float(resp.json()["price"])


def _from_coingecko(symbol: str) -> float | None:
    slug = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}.get(symbol.upper())
    if not slug:
        return None
    resp = httpx.get(f"https://api.coingecko.com/api/v3/simple/price", params={"ids": slug, "vs_currencies": "usd"}, timeout=5)
    resp.raise_for_status()
    return resp.json()[slug]["usd"]
