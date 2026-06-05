"""Semi-auto trading: route signals to approval queue or paper trader based on mode."""
import structlog
from app.config import settings
from app.trading.signal import Signal
from app.risk.position_sizing import kelly_size
from app.risk.kill_switch import any_active

log = structlog.get_logger()


def route_signal(signal: Signal, bankroll: float = 1000.0) -> dict:
    """
    Route a signal based on APP_MODE:
      research   → log only, no trade
      paper      → enter paper trade immediately
      semi_auto  → submit to approval queue
      live       → blocked until Phase 6

    Returns a result dict describing what happened.
    """
    if any_active():
        return {"action": "blocked", "reason": "kill switch active"}

    mode = settings.app_mode
    from app.compliance import check_compliance
    try:
        check_compliance(mode)
    except RuntimeError as e:
        return {"action": "blocked", "reason": str(e)}

    if mode == "research":
        log.info("signal_research_only", signal_id=signal.signal_id,
                 question=signal.market_question[:60])
        return {"action": "logged", "mode": "research", "signal_id": signal.signal_id}

    if mode == "paper":
        from app.trading.paper_trader import enter_trade
        signal.mode = "paper"
        trade = enter_trade(signal)
        return {"action": "paper_trade_entered", "trade": trade, "signal_id": signal.signal_id}

    if mode == "semi_auto":
        from app.trading.approval_queue import submit_for_approval
        kelly = kelly_size(signal.estimated_edge, bankroll)
        signal.recommended_position_size = kelly["recommended_size_usd"]
        req = submit_for_approval(signal, kelly)
        return {"action": "submitted_for_approval", "request_id": req["request_id"],
                "signal_id": signal.signal_id}

    if mode == "live":
        return {"action": "blocked",
                "reason": "Live execution not yet enabled — Phase 6 only. "
                          "Complete pre-live checklist first."}

    return {"action": "unknown_mode", "mode": mode}


def execute_approved(request_id: str) -> dict:
    """
    Execute an approved request in paper mode (Phase 5) or live (Phase 6).
    Phase 5 always routes to paper trade — live execution is Phase 6.
    """
    from app.trading.approval_queue import get_all_requests
    from app.trading.paper_trader import enter_trade, PaperTrade
    from app.trading.signal import Signal
    from datetime import datetime, timezone

    reqs = {r["request_id"]: r for r in get_all_requests()}
    req = reqs.get(request_id)
    if not req or req["status"] != "APPROVED":
        return {"success": False, "reason": "Request not found or not approved"}

    # Reconstruct minimal signal for paper trade entry
    sig = Signal(
        signal_id=req["signal_id"],
        timestamp=datetime.now(timezone.utc),
        market_id=req["market_id"],
        market_question=req["market_question"],
        sector="crypto",
        market_type=req["market_type"],
        strategy_name="semi_auto",
        recommended_side=req["recommended_side"],
        polymarket_price=req["polymarket_price"],
        model_fair_probability=req["model_fair_probability"],
        estimated_edge=req["estimated_edge"],
        confidence_score=req["confidence_score"],
        resolution_source_match_score=req["resolution_source_match_score"],
        recommended_position_size=req["recommended_size_usd"],
        reason_for_signal=req["reason_for_signal"],
        invalidating_conditions=req["invalidating_conditions"],
        mode="paper",  # Phase 5 always paper; Phase 6 will use "live"
        liquidity_score=0.5,
    )

    trade = enter_trade(sig)
    if trade:
        log.info("approved_trade_executed", request_id=request_id,
                 trade_id=trade["trade_id"])
        return {"success": True, "trade": trade, "request_id": request_id}
    return {"success": False, "reason": "Trade entry failed"}
