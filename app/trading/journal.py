"""Trade journal: log and retrieve paper trades."""
from app.database import PaperTrade, get_session, init_db
import structlog

log = structlog.get_logger()


def log_resolution(market_id: str, outcome: str, model_prob: float | None = None,
                   market_price: float | None = None) -> None:
    """Record a market resolution event and close any open trades for that market."""
    from app.database import ResolutionEvent
    from datetime import datetime, timezone
    init_db()

    brier = None
    cal_error = None
    if model_prob is not None:
        outcome_val = 1.0 if outcome == "YES" else 0.0
        brier = (model_prob - outcome_val) ** 2
        cal_error = abs(model_prob - outcome_val)

    event = ResolutionEvent(
        market_id=market_id,
        resolved_at=datetime.now(timezone.utc),
        resolved_outcome=outcome,
        model_probability_at_resolution=model_prob,
        market_price_at_resolution=market_price,
        calibration_error=cal_error,
        brier_score=brier,
    )

    with get_session() as session:
        session.add(event)

    # Close any open paper trades for this market
    from app.trading.paper_trader import close_trade, get_open_trades
    for trade in get_open_trades():
        if trade.market_id == market_id:
            exit_price = 1.0 if outcome == "YES" else 0.0
            close_trade(trade.trade_id, exit_price, "resolution", final_outcome=outcome)

    log.info("resolution_logged", market_id=market_id, outcome=outcome, brier=brier)
