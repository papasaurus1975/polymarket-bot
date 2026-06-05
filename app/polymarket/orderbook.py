"""Orderbook parsing and spread calculation."""


def parse_spread(orderbook: dict) -> dict:
    """Extract best bid, best ask, and spread from a raw CLOB orderbook response."""
    bids = orderbook.get("bids", [])
    asks = orderbook.get("asks", [])
    best_bid = float(bids[0]["price"]) if bids else None
    best_ask = float(asks[0]["price"]) if asks else None
    spread = (best_ask - best_bid) if (best_bid and best_ask) else None
    return {"best_bid": best_bid, "best_ask": best_ask, "spread": spread}
