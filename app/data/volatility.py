"""Realized and implied volatility calculation."""
import numpy as np
from app.data.crypto_prices import get_historical_prices
import structlog

log = structlog.get_logger()


def realized_vol(prices: list[float], window: int = 30) -> float:
    """Annualized realized volatility from a daily price series."""
    if len(prices) < 2:
        raise ValueError("Need at least 2 prices")
    arr = np.array(prices[-window - 1:])
    log_returns = np.diff(np.log(arr))
    if len(log_returns) < 2:
        raise ValueError(f"Need at least 2 log returns, got {len(log_returns)}")
    return float(np.std(log_returns, ddof=1) * np.sqrt(365))


def get_realized_vol(symbol: str, window: int = 30) -> float:
    """Fetch historical prices and return annualized realized vol."""
    try:
        prices = get_historical_prices(symbol, days=window + 5)
        vol = realized_vol(prices, window=window)
        log.info("realized_vol_calculated", symbol=symbol, vol=round(vol, 4))
        return vol
    except Exception as e:
        log.warning("vol_calc_failed", symbol=symbol, error=str(e))
        # Sector-average fallback per the PDF
        return _sector_average_vol(symbol)


def _sector_average_vol(symbol: str) -> float:
    """Fallback: historical average volatility by asset class."""
    defaults = {"BTC": 0.65, "ETH": 0.75, "SOL": 0.90, "XRP": 0.80}
    vol = defaults.get(symbol.upper(), 0.80)
    log.warning("vol_using_fallback", symbol=symbol, fallback_vol=vol)
    return vol
