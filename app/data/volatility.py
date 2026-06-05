"""Realized and implied volatility calculation. Phase 2+."""


def realized_vol(prices: list[float], window: int = 30) -> float:
    """Annualized realized volatility from a price series."""
    import numpy as np
    returns = np.diff(np.log(prices))
    return float(np.std(returns[-window:]) * np.sqrt(365))
