"""Strategy 1: Crypto Probability Mispricing. Phase 2+."""
from app.strategies.base import BaseStrategy


class CryptoProbabilityStrategy(BaseStrategy):
    def generate_signal(self, market: dict, prices: dict) -> dict | None:
        raise NotImplementedError("Phase 2")
