"""Strategy 3: Closing Convergence (near-resolution trades). Phase 3+."""
from app.strategies.base import BaseStrategy


class ClosingConvergenceStrategy(BaseStrategy):
    def generate_signal(self, market: dict, prices: dict) -> dict | None:
        raise NotImplementedError("Phase 3")
