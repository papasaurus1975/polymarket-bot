"""Strategy 4: News/Event Shock Detection. Phase 4+."""
from app.strategies.base import BaseStrategy


class NewsShockStrategy(BaseStrategy):
    def generate_signal(self, market: dict, prices: dict) -> dict | None:
        raise NotImplementedError("Phase 4")
