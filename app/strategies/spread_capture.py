"""Strategy 2: Spread Capture / Market Making. Phase 3+."""
from app.strategies.base import BaseStrategy


class SpreadCaptureStrategy(BaseStrategy):
    def generate_signal(self, market: dict, prices: dict) -> dict | None:
        raise NotImplementedError("Phase 3")
