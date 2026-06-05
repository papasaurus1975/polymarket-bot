"""On-chain position reconciler: detect ghost and phantom positions (Section 17.3).

Ghost positions:  exist on-chain but NOT in local DB → import before trading resumes.
Phantom positions: exist in DB but NOT on-chain → usually a missed fill → halt + alert.

This module is the authoritative safety check before any live trade.
"""
import structlog
from datetime import datetime, timezone
from app.database import get_session, init_db, PaperTrade, RiskEvent
from app.polymarket.execution import get_positions

log = structlog.get_logger()


def reconcile(wallet_address: str) -> dict:
    """
    Compare local DB positions against on-chain positions.
    Returns a reconciliation report.

    On mismatch: HALT new trade generation, alert user, log CRITICAL risk event.
    """
    init_db()

    # Fetch on-chain positions
    try:
        onchain = get_positions(wallet_address)
        onchain_ids = {p.get("conditionId") or p.get("market_id"): p
                       for p in onchain if p}
    except Exception as e:
        log.error("reconcile_onchain_fetch_failed", error=str(e))
        _log_risk_event("RECONCILE_FETCH_FAILED", str(e), severity="HIGH")
        return {"status": "ERROR", "error": str(e)}

    # Fetch local open positions
    with get_session() as session:
        local_open = session.query(PaperTrade).filter(
            PaperTrade.status == "OPEN"
        ).all()
        local_ids = {t.market_id: t for t in local_open}
        session.expunge_all()

    # Detect ghost positions (on-chain but not in DB)
    ghost_ids = set(onchain_ids) - set(local_ids)

    # Detect phantom positions (in DB but not on-chain)
    phantom_ids = set(local_ids) - set(onchain_ids)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "wallet": wallet_address,
        "onchain_count": len(onchain_ids),
        "local_count": len(local_ids),
        "ghost_positions": list(ghost_ids),
        "phantom_positions": list(phantom_ids),
        "status": "OK",
        "action_required": False,
    }

    if ghost_ids:
        msg = f"Ghost positions detected: {ghost_ids}"
        log.warning("ghost_positions_detected", ids=list(ghost_ids))
        _log_risk_event("GHOST_POSITIONS", msg, severity="HIGH")
        report["status"] = "MISMATCH"
        report["action_required"] = True
        report["message"] = (
            "Ghost positions exist on-chain but not in local DB. "
            "Import them before trading resumes."
        )

    if phantom_ids:
        msg = f"Phantom positions detected: {phantom_ids}"
        log.error("phantom_positions_detected", ids=list(phantom_ids))
        _log_risk_event("PHANTOM_POSITIONS", msg, severity="CRITICAL")
        report["status"] = "CRITICAL_MISMATCH"
        report["action_required"] = True
        report["message"] = (
            "Phantom positions exist in DB but NOT on-chain. "
            "This usually indicates a fill that was not recorded. "
            "Manual reconciliation required before trading resumes."
        )
        # Trip kill switch
        from app.risk.kill_switch import activate
        activate("live_trading",
                 reason=f"phantom positions detected: {phantom_ids}")

    if report["status"] == "OK":
        log.info("reconciliation_ok", onchain=len(onchain_ids),
                 local=len(local_ids))

    return report


def import_ghost_position(market_id: str, wallet_address: str) -> dict | None:
    """Import a ghost position from on-chain into the local DB."""
    try:
        from app.polymarket.execution import get_positions
        positions = get_positions(wallet_address)
        match = next((p for p in positions
                      if p.get("conditionId") == market_id or
                         p.get("market_id") == market_id), None)
        if not match:
            return None

        init_db()
        trade = PaperTrade(
            trade_id=f"ghost_{market_id[:8]}",
            signal_id="ghost_import",
            market_id=market_id,
            market_question=match.get("title", market_id),
            market_type="?",
            strategy_name="ghost_import",
            entry_time=datetime.now(timezone.utc),
            entry_price=float(match.get("avgPrice", 0)),
            side=match.get("side", "YES"),
            size=float(match.get("size", 0)),
            model_probability_at_entry=0.5,
            market_probability_at_entry=float(match.get("avgPrice", 0)),
            edge_at_entry=0.0,
            resolution_source_match_score=0.0,
            status="OPEN",
            notes="Imported from on-chain ghost position detection",
        )
        with get_session() as s:
            s.add(trade)

        log.info("ghost_position_imported", market_id=market_id)
        _log_risk_event("GHOST_IMPORTED",
                        f"Ghost position imported for {market_id}", severity="MEDIUM")
        return {"market_id": market_id, "imported": True}
    except Exception as e:
        log.error("ghost_import_failed", market_id=market_id, error=str(e))
        return None


def _log_risk_event(event_type: str, description: str, severity: str = "MEDIUM"):
    init_db()
    event = RiskEvent(
        event_type=event_type,
        severity=severity,
        description=description,
        action_taken="Kill switch tripped" if severity == "CRITICAL" else "Alert sent",
    )
    try:
        with get_session() as s:
            s.add(event)
    except Exception as e:
        log.error("risk_event_log_failed", error=str(e))
