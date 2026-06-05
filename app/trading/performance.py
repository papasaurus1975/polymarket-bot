"""P&L metrics, win rate, and model calibration (Brier score).

Accepts list[dict] as returned by get_all_trades() / get_open_trades().
"""
import math


def compute_metrics(trades: list[dict]) -> dict:
    """Return performance summary dict from a list of trade dicts."""
    closed = [t for t in trades if t.get("status") == "CLOSED" and t.get("profit_loss") is not None]
    if not closed:
        return _empty_metrics(open_count=sum(1 for t in trades if t.get("status") == "OPEN"))

    pnls = [t["profit_loss"] for t in closed]
    total_pnl = round(sum(pnls), 4)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    win_rate = len(wins) / len(closed)
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else None

    calibrated = [t for t in closed if t.get("calibration_error") is not None]
    brier = _brier_score(calibrated) if calibrated else None
    avg_cal_error = round(sum(t["calibration_error"] for t in calibrated) / len(calibrated), 4) if calibrated else None

    sharpe = _sharpe(pnls)

    by_type: dict[str, dict] = {}
    for t in closed:
        mt = t.get("market_type") or "?"
        by_type.setdefault(mt, {"pnl": 0.0, "count": 0, "wins": 0})
        by_type[mt]["pnl"] += t["profit_loss"]
        by_type[mt]["count"] += 1
        if t["profit_loss"] > 0:
            by_type[mt]["wins"] += 1

    return {
        "total_trades": len(closed),
        "open_trades": sum(1 for t in trades if t.get("status") == "OPEN"),
        "total_pnl": total_pnl,
        "win_rate": round(win_rate, 4),
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
        "profit_factor": round(profit_factor, 2) if profit_factor is not None else None,
        "sharpe": round(sharpe, 3) if sharpe else None,
        "brier_score": round(brier, 4) if brier else None,
        "avg_calibration_error": avg_cal_error,
        "by_type": by_type,
    }


def _brier_score(trades: list[dict]) -> float:
    total = 0.0
    for t in trades:
        outcome = 1.0 if t.get("final_outcome") == "YES" else 0.0
        total += (t["model_probability_at_entry"] - outcome) ** 2
    return total / len(trades)


def _sharpe(pnls: list[float], risk_free: float = 0.0) -> float | None:
    if len(pnls) < 2:
        return None
    mean = sum(pnls) / len(pnls)
    variance = sum((p - mean) ** 2 for p in pnls) / (len(pnls) - 1)
    std = math.sqrt(variance)
    if std == 0:
        return None
    return (mean - risk_free) / std


def _empty_metrics(open_count: int = 0) -> dict:
    return {
        "total_trades": 0, "open_trades": open_count, "total_pnl": 0.0,
        "win_rate": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
        "profit_factor": None, "sharpe": None,
        "brier_score": None, "avg_calibration_error": None, "by_type": {},
    }
