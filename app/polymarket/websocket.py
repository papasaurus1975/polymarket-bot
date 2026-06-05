"""CLOB WebSocket feed with exponential-backoff reconnection. Phase 1+."""

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


async def subscribe(token_ids: list[str], on_message):
    """Connect to CLOB WebSocket and stream orderbook updates. Phase 2+."""
    raise NotImplementedError("WebSocket feed — Phase 2")
