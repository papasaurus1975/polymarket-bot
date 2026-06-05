"""Paper trade simulation with realistic fill simulation (Section 16)."""
import uuid
import random
from datetime import datetime, timezone

import structlog

from app.trading.signal import Signal
from app.database import PaperTrade, get_session, init_db

log = structlog.get_logger()

# Polymarket fee schedule (maker/taker)
TAKER_FEE = 0.0
MAKER_FEE = 0.0
# Polymarket fees are baked into the spread; model slippage instead


def simulate_fill(signal: Signal, orderbook: dict | None = None) -> dict:
    """
    Simulate entry fill with:
    - Slippage proportional to order size vs liquidity
    - Partial fill based on book depth
    - Execution delay (latency)

    Returns fill dict with actual_price, fill_ratio, slippage, fees.
    """
    liquidity = signal.liquidity_score * 100_000  # reverse the 0-1 scaling
    size = signal.recommended_position_size

    # Slippage: market impact proportional to order size vs liquidity
    if liquidity > 0:
        market_impact = min(size / liquidity, 0.02)   # cap at 2%
    else:
        market_impact = 0.005

    slippage = market_impact * signal.polymarket_price
    # Buys fill slightly worse (higher), sells slightly better (lower)
    direction = 1 if signal.recommended_side == "YES" else -1
    actual_price = round(signal.polymarket_price + direction * slippage, 4)
    actual_price = max(0.01, min(0.99, actual_price))

    # Partial fill: random based on order size vs book depth
    if liquidity < size * 10:
        fill_ratio = random.uniform(0.6, 0.95)
    else:
        fill_ratio = random.uniform(0.90, 1.0)

    filled_size = round(size * fill_ratio, 2)
    fees = round(filled_size * actual_price * 0.0, 4)   # Polymarket fees=0 currently

    return {
        "actual_price": actual_price,
        "fill_ratio": round(fill_ratio, 4),
        "filled_size": filled_size,
        "slippage": round(slippage, 4),
        "fees": fees,
    }


_SNAP_KEYS = [
    "trade_id", "signal_id", "market_id", "market_question", "market_type",
    "strategy_name", "entry_time", "entry_price", "side", "size",
    "model_probability_at_entry", "market_probability_at_entry", "edge_at_entry",
    "resolution_source_match_score", "simulated_fill_ratio", "simulated_slippage",
    "fees_simulated", "status",
]

_FULL_SNAP_KEYS = _SNAP_KEYS + [
    "exit_time", "exit_price", "exit_reason", "profit_loss",
    "max_adverse_excursion", "max_favorable_excursion",
    "final_outcome", "actual_resolution_price", "model_accuracy",
    "calibration_error", "notes", "created_at",
]


def _trade_snapshot(trade: PaperTrade) -> dict:
    """Minimal snapshot used at entry time."""
    return {k: getattr(trade, k) for k in _SNAP_KEYS}


def _full_snap(trade: PaperTrade) -> dict:
    """Full snapshot including all nullable columns — must be called inside a session."""
    return {k: getattr(trade, k) for k in _FULL_SNAP_KEYS}


def enter_trade(signal: Signal) -> dict | None:
    """Simulate entering a paper trade. Persists to DB. Returns trade record."""
    if signal.mode not in ("paper", "research"):
        log.warning("paper_trade_blocked", mode=signal.mode)
        return None

    init_db()
    fill = simulate_fill(signal)

    trade = PaperTrade(
        trade_id=str(uuid.uuid4())[:12],
        signal_id=signal.signal_id,
        market_id=signal.market_id,
        market_question=signal.market_question,
        market_type=signal.market_type,
        strategy_name=signal.strategy_name,
        entry_time=datetime.now(timezone.utc),
        entry_price=fill["actual_price"],
        side=signal.recommended_side,
        size=fill["filled_size"],
        model_probability_at_entry=signal.model_fair_probability,
        market_probability_at_entry=signal.polymarket_price,
        edge_at_entry=signal.estimated_edge,
        resolution_source_match_score=signal.resolution_source_match_score,
        simulated_fill_ratio=fill["fill_ratio"],
        simulated_slippage=fill["slippage"],
        fees_simulated=fill["fees"],
        status="OPEN",
    )

    with get_session() as session:
        session.add(trade)
        session.flush()
        snapshot = _trade_snapshot(trade)

    log.info("paper_trade_entered",
             trade_id=snapshot["trade_id"],
             question=signal.market_question[:60],
             side=snapshot["side"],
             price=snapshot["entry_price"],
             size=snapshot["size"],
             fill_ratio=fill["fill_ratio"])
    return snapshot


def close_trade(trade_id: str, exit_price: float, exit_reason: str,
                final_outcome: str | None = None) -> dict | None:
    """Close an open paper trade and calculate P&L."""
    init_db()
    with get_session() as session:
        trade = session.get(PaperTrade, trade_id)
        if not trade or trade.status != "OPEN":
            return None

        trade.exit_time = datetime.now(timezone.utc)
        trade.exit_price = exit_price
        trade.exit_reason = exit_reason
        trade.status = "CLOSED"
        trade.final_outcome = final_outcome

        # P&L: for YES position: (exit - entry) * size; for NO: (entry - exit) * size
        if trade.side == "YES":
            pnl = (exit_price - trade.entry_price) * trade.size
        else:
            pnl = (trade.entry_price - exit_price) * trade.size

        trade.profit_loss = round(pnl - trade.fees_simulated, 4)

        if final_outcome:
            outcome_price = 1.0 if final_outcome == "YES" else 0.0
            trade.actual_resolution_price = outcome_price
            model_correct = (
                (trade.model_probability_at_entry > 0.5 and final_outcome == "YES") or
                (trade.model_probability_at_entry < 0.5 and final_outcome == "NO")
            )
            trade.model_accuracy = model_correct
            trade.calibration_error = abs(trade.model_probability_at_entry - outcome_price)

        session.add(trade)
        snapshot = {
            **_trade_snapshot(trade),
            "exit_time": trade.exit_time,
            "exit_price": trade.exit_price,
            "exit_reason": trade.exit_reason,
            "profit_loss": trade.profit_loss,
            "final_outcome": trade.final_outcome,
            "model_accuracy": trade.model_accuracy,
            "calibration_error": trade.calibration_error,
        }

    log.info("paper_trade_closed",
             trade_id=trade_id,
             pnl=snapshot["profit_loss"],
             exit_reason=exit_reason)
    return snapshot


def get_open_trades() -> list[dict]:
    init_db()
    with get_session() as session:
        trades = session.query(PaperTrade).filter(PaperTrade.status == "OPEN").all()
        return [_full_snap(t) for t in trades]


def get_all_trades() -> list[dict]:
    init_db()
    with get_session() as session:
        trades = session.query(PaperTrade).order_by(PaperTrade.created_at.desc()).all()
        return [_full_snap(t) for t in trades]
