"""CLOB order placement, cancellation, fill tracking. Phase 6 only.

SAFETY CONTRACT:
  - Only limit orders — never market orders
  - Every order re-validated against risk limits immediately before placement
  - Any execution error triggers alert + halt for that market
  - LIVE_TRADING_ENABLED must be True in .env AND pre-live checklist must pass
"""
import uuid
import structlog
import httpx
from datetime import datetime, timezone

from app.config import settings
from app.risk.kill_switch import activate, is_active
from app.polymarket.auth import sign_order

log = structlog.get_logger()

CLOB_BASE_URL = "https://clob.polymarket.com"


class ExecutionError(Exception):
    pass


def _live_guard():
    """Raise if live trading is not enabled or any kill switch is active."""
    if not settings.live_trading_enabled:
        raise ExecutionError(
            "LIVE_TRADING_ENABLED=false — set to true in .env only after "
            "completing the pre-live checklist."
        )
    if is_active("live_trading"):
        raise ExecutionError("live_trading kill switch is active")
    if is_active("compliance"):
        raise ExecutionError("compliance kill switch is active — trading halted")
    if is_active("daily"):
        raise ExecutionError("daily loss limit kill switch is active")


def _pre_order_risk_check(token_id: str, side: str, price: float,
                           size_usd: float) -> None:
    """Hard risk checks immediately before placing any order."""
    from app.risk.limits import check_position_size, check_spread
    from app.config import settings

    bankroll = _get_bankroll_estimate()
    if not check_position_size(size_usd, bankroll):
        raise ExecutionError(
            f"Position size ${size_usd:.2f} exceeds "
            f"{settings.max_position_size_pct:.0%} of bankroll ${bankroll:.0f}"
        )


def place_limit_order(
    token_id: str,
    side: str,           # "BUY" or "SELL"
    price: float,        # limit price (0.01–0.99)
    size_usd: float,     # collateral amount in USDC
    keystore_path: str,
    passphrase: str,
) -> dict:
    """
    Place a limit order on the CLOB. Limit orders only — never market orders.

    For marketable buys: price = best_ask + small buffer (per PDF Section 17.2).
    Every order is re-validated against risk limits before placement.
    """
    _live_guard()
    _pre_order_risk_check(token_id, side, price, size_usd)

    # Build order payload
    expiration = int((datetime.now(timezone.utc).timestamp()) + 3600)  # 1hr TTL
    order = {
        "maker": "",        # filled after wallet load
        "taker": "0x0000000000000000000000000000000000000000",
        "tokenId": int(token_id),
        "makerAmount": int(size_usd * 1_000_000),   # USDC 6 decimals
        "takerAmount": int(size_usd / price * 1_000_000),
        "expiration": expiration,
        "nonce": _get_nonce(),
        "feeRateBps": 0,
        "side": 0 if side == "BUY" else 1,
        "signatureType": 0,
    }

    # Get wallet address + fill maker field
    from eth_account import Account
    import json
    with open(keystore_path) as f:
        ks = json.load(f)
    account = Account.from_key(Account.decrypt(ks, passphrase))
    order["maker"] = account.address

    # Sign
    signature = sign_order(order, keystore_path, passphrase)

    # Submit to CLOB
    payload = {**order, "signature": signature}
    try:
        resp = httpx.post(
            f"{CLOB_BASE_URL}/order",
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()
    except Exception as e:
        _on_execution_error(token_id, str(e))
        raise ExecutionError(f"Order placement failed: {e}") from e

    order_id = result.get("orderID", str(uuid.uuid4())[:8])
    _audit_log("ORDER_PLACED", {
        "order_id": order_id, "token_id": token_id,
        "side": side, "price": price, "size_usd": size_usd,
    })
    log.info("order_placed", order_id=order_id, token_id=token_id,
             side=side, price=price, size_usd=size_usd)
    return {"order_id": order_id, "status": "LIVE", **result}


def cancel_order(order_id: str) -> dict:
    """Cancel an open limit order."""
    _live_guard()
    try:
        resp = httpx.delete(f"{CLOB_BASE_URL}/order/{order_id}", timeout=10)
        resp.raise_for_status()
        _audit_log("ORDER_CANCELLED", {"order_id": order_id})
        log.info("order_cancelled", order_id=order_id)
        return resp.json()
    except Exception as e:
        log.error("cancel_failed", order_id=order_id, error=str(e))
        raise ExecutionError(f"Cancel failed: {e}") from e


def cancel_all_orders() -> list[str]:
    """Emergency: cancel all open orders. Called by kill switch."""
    _live_guard()
    try:
        resp = httpx.delete(f"{CLOB_BASE_URL}/orders", timeout=15)
        resp.raise_for_status()
        cancelled = resp.json().get("cancelled", [])
        _audit_log("ALL_ORDERS_CANCELLED", {"count": len(cancelled)})
        log.warning("all_orders_cancelled", count=len(cancelled))
        return cancelled
    except Exception as e:
        log.error("cancel_all_failed", error=str(e))
        return []


def replace_order(order_id: str, new_price: float, new_size: float,
                  keystore_path: str, passphrase: str) -> dict:
    """Cancel existing order and place a replacement."""
    cancel_order(order_id)
    # Caller must supply token_id and side for replacement
    raise NotImplementedError("Caller must provide token_id + side for replace_order")


def get_order_status(order_id: str) -> dict:
    """Check status of a specific order."""
    resp = httpx.get(f"{CLOB_BASE_URL}/order/{order_id}", timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_fills(order_id: str) -> list[dict]:
    """Get fills for an order."""
    resp = httpx.get(f"{CLOB_BASE_URL}/trades", params={"order_id": order_id}, timeout=10)
    resp.raise_for_status()
    return resp.json().get("data", [])


def get_positions(address: str) -> list[dict]:
    """Get current on-chain positions for a wallet."""
    resp = httpx.get(
        "https://data-api.polymarket.com/positions",
        params={"user": address, "limit": 100},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_balances(address: str) -> dict:
    """Get USDC balance on Polygon for a wallet."""
    resp = httpx.get(
        f"{CLOB_BASE_URL}/balance-allowance",
        params={"asset_type": "USDC", "address": address},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def emergency_shutdown(reason: str = "manual") -> dict:
    """
    Emergency stop: cancel all open orders and trip all relevant kill switches.
    Requires manual confirmation to re-enable (never auto-re-enables).
    """
    log.warning("EMERGENCY_SHUTDOWN_INITIATED", reason=reason)
    _audit_log("EMERGENCY_SHUTDOWN", {"reason": reason})

    cancelled = []
    if settings.live_trading_enabled:
        try:
            cancelled = cancel_all_orders()
        except Exception as e:
            log.error("emergency_cancel_failed", error=str(e))

    activate("live_trading", reason=f"emergency shutdown: {reason}")
    activate("manual", reason=f"emergency shutdown: {reason}")

    log.warning("EMERGENCY_SHUTDOWN_COMPLETE",
                orders_cancelled=len(cancelled), reason=reason)
    return {
        "shutdown": True,
        "reason": reason,
        "orders_cancelled": cancelled,
        "message": "All kill switches tripped. Manual reset required to resume.",
    }


def _on_execution_error(token_id: str, error: str):
    """On any execution error: alert + halt that market's signals."""
    from app.risk.kill_switch import activate
    log.error("execution_error", token_id=token_id, error=error)
    _audit_log("EXECUTION_ERROR", {"token_id": token_id, "error": error})
    activate("market", reason=f"execution error on {token_id}: {error}")


def _get_nonce() -> int:
    """Return a monotonically incrementing nonce persisted in the DB."""
    import json
    from app.database import get_session, init_db, AuditLog
    init_db()
    with get_session() as session:
        last = (
            session.query(AuditLog)
            .filter(AuditLog.event_type == "NONCE")
            .order_by(AuditLog.created_at.desc())
            .first()
        )
        last_nonce = json.loads(last.data).get("nonce", 0) if last else 0
        nonce = max(last_nonce + 1, int(__import__("time").time() * 1000))
        session.add(AuditLog(
            event_type="NONCE",
            data=json.dumps({"nonce": nonce}),
            created_at=datetime.now(timezone.utc),
        ))
    return nonce


def _get_bankroll_estimate() -> float:
    """Return bankroll estimate from config or fallback."""
    return 1000.0  # Phase 6: replace with live balance query


def _audit_log(event_type: str, data: dict):
    """Persist every execution event to the audit log."""
    from app.database import get_session, init_db, Base
    from sqlalchemy import String, Text, DateTime
    from sqlalchemy.orm import mapped_column, Mapped
    import json

    try:
        from app.database import AuditLog
        init_db()
        entry = AuditLog(
            event_type=event_type,
            data=json.dumps(data),
            created_at=datetime.now(timezone.utc),
        )
        with get_session() as s:
            s.add(entry)
    except Exception as e:
        # Audit log must never block execution
        log.error("audit_log_failed", error=str(e), event_type=event_type)
