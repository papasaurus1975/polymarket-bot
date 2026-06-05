"""Gamma REST API client — market metadata, questions, categories, history."""
import httpx

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"


class GammaClient:
    def __init__(self):
        self._client = httpx.Client(base_url=GAMMA_BASE_URL, timeout=15.0)

    def get_markets(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Fetch active markets from the Gamma API."""
        resp = self._client.get("/markets", params={"limit": limit, "offset": offset, "active": "true", "closed": "false"})
        resp.raise_for_status()
        return resp.json()

    def get_events(self, limit: int = 100, offset: int = 0, category: str = "") -> list[dict]:
        """Fetch events (groups of markets). Use category='Crypto' for crypto events."""
        params = {"limit": limit, "offset": offset, "active": "true", "closed": "false"}
        if category:
            params["category"] = category
        resp = self._client.get("/events", params=params)
        resp.raise_for_status()
        return resp.json()

    def get_market(self, market_id: str) -> dict:
        resp = self._client.get(f"/markets/{market_id}")
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._client.close()
