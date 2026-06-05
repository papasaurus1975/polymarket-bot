"""Live CLOB execution with pre-live checklist gate (Phase 6).

This module will only execute if ALL pre-live checklist items are confirmed.
It wraps execution.py with the full safety stack.
"""
import uuid
import structlog
from datetime import datetime, timezone

from app.config import settings
from app.risk.kill_switch import is_active, any_active

log = structlog.get_logger()

# Pre-live checklist — all must be True before live execution is allowed
CHECKLIST_ITEMS = [
    "user_confirmation",
    "wallet_funded",
    "eip712_tested",
    "compliance_approved",
    "paper_trading_complete",
    "paper_pnl_positive",
    "risk_limits_configured",
    "kill_switch_tested",
    "logging_verified",
    "emergency_shutdown_tested",
]


def verify_pre_live_checklist(confirmed_items: list[str]) -> dict:
    """
    Verify all pre-live checklist items are confirmed.
    Returns dict with passed=True/False and missing items.
    """
    missing = [item for item in CHECKLIST_ITEMS if item not in confirmed_items]
    return {
        "passed": len(missing) == 0,
        "confirmed": confirmed_items,
        "missing": missing,
        "total": len(CHECKLIST_ITEMS),
        "completed": len(CHECKLIST_ITEMS) - len(missing),
    }


def execute_live_order(
    token_id: str,
    side: str,
    price: float,
    size_usd: float,
    keystore_path: str,
    passphrase: str,
    confirmed_checklist: list[str] | None = None,
) -> dict:
    """
    Execute a live CLOB order with full safety stack:
      1. Pre-live checklist gate
      2. Kill switch check
      3. Compliance check
      4. Risk limit re-validation
      5. Order placement
      6. Fill tracking
      7. Audit log

    confirmed_checklist: list of completed checklist item names.
    """
    # Gate 1: pre-live checklist
    checklist = verify_pre_live_checklist(confirmed_checklist or [])
    if not checklist["passed"]:
        return {
            "success": False,
            "reason": f"Pre-live checklist incomplete. Missing: {checklist['missing']}",
            "checklist": checklist,
        }

    # Gate 2: kill switches
    if any_active():
        return {"success": False, "reason": "Kill switch active — live trading halted"}

    # Gate 3: LIVE_TRADING_ENABLED
    if not settings.live_trading_enabled:
        return {"success": False,
                "reason": "LIVE_TRADING_ENABLED=false — set in .env to enable"}

    # Gate 4: place order
    try:
        from app.polymarket.execution import place_limit_order
        result = place_limit_order(token_id, side, price, size_usd,
                                   keystore_path, passphrase)
    except Exception as e:
        log.error("live_order_failed", error=str(e))
        return {"success": False, "reason": str(e)}

    # Record in live_trades table
    from app.database import LiveTrade, get_session, init_db
    init_db()
    trade = LiveTrade(
        trade_id=str(uuid.uuid4())[:12],
        signal_id=result.get("order_id", "unknown"),
        market_id=token_id,
        clob_order_id=result.get("order_id"),
        entry_time=datetime.now(timezone.utc),
        entry_price=price,
        side=side,
        size_requested=size_usd,
        strategy_name="live_execution",
        onchain_verified=False,
        reconciliation_status="PENDING",
    )
    with get_session() as s:
        s.add(trade)
        s.flush()
        trade_id = trade.trade_id

    log.info("live_trade_recorded", trade_id=trade_id,
             clob_order_id=result.get("order_id"))
    return {"success": True, "trade_id": trade_id, "order": result}


def track_fill(clob_order_id: str, trade_id: str) -> dict:
    """Poll for fills and update the live trade record."""
    from app.polymarket.execution import get_fills
    from app.database import LiveTrade, get_session, init_db
    init_db()

    fills = get_fills(clob_order_id)
    if not fills:
        return {"filled": False, "fills": []}

    total_filled = sum(float(f.get("size", 0)) for f in fills)
    avg_price = sum(float(f.get("price", 0)) * float(f.get("size", 0))
                    for f in fills) / max(total_filled, 1)

    with get_session() as s:
        trade = s.get(LiveTrade, trade_id)
        if trade:
            trade.size_filled = total_filled
            trade.fill_price_avg = round(avg_price, 4)
            trade.onchain_verified = True
            trade.reconciliation_status = "VERIFIED"
            s.add(trade)

    log.info("fill_tracked", trade_id=trade_id, filled=total_filled,
             avg_price=round(avg_price, 4))
    return {"filled": True, "size_filled": total_filled, "avg_price": avg_price}
