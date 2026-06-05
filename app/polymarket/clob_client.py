"""CLOB REST API client — live orderbook, pricing, order execution."""
import httpx

CLOB_BASE_URL = "https://clob.polymarket.com"


class ClobClient:
    def __init__(self):
        self._client = httpx.Client(base_url=CLOB_BASE_URL, timeout=10.0)

    def get_orderbook(self, token_id: str) -> dict:
        """Fetch the orderbook for a given condition token."""
        resp = self._client.get("/book", params={"token_id": token_id})
        resp.raise_for_status()
        return resp.json()

    def get_price(self, token_id: str, side: str = "buy") -> float | None:
        """Get best price for YES token. side = 'buy' | 'sell'."""
        resp = self._client.get("/price", params={"token_id": token_id, "side": side})
        resp.raise_for_status()
        data = resp.json()
        return float(data.get("price")) if data.get("price") else None

    def get_spread(self, token_id: str) -> dict:
        """Return bid, ask, and spread for a token."""
        resp = self._client.get("/spread", params={"token_id": token_id})
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._client.close()
