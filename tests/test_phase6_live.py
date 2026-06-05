"""Tests for Phase 6: live execution gate, reconciler, checklist, emergency shutdown."""
import pytest
from app.trading.live_trader import verify_pre_live_checklist, CHECKLIST_ITEMS
from app.polymarket.execution import emergency_shutdown, ExecutionError


# ── Pre-live checklist ───────────────────────────────────────────────────────

def test_checklist_all_missing():
    result = verify_pre_live_checklist([])
    assert result["passed"] is False
    assert len(result["missing"]) == len(CHECKLIST_ITEMS)


def test_checklist_all_confirmed():
    result = verify_pre_live_checklist(CHECKLIST_ITEMS)
    assert result["passed"] is True
    assert result["missing"] == []


def test_checklist_partial():
    confirmed = CHECKLIST_ITEMS[:5]
    result = verify_pre_live_checklist(confirmed)
    assert result["passed"] is False
    assert result["completed"] == 5
    assert result["total"] == len(CHECKLIST_ITEMS)


# ── Live order gate ──────────────────────────────────────────────────────────

def test_live_order_blocked_without_checklist(monkeypatch):
    monkeypatch.setattr("app.trading.live_trader.settings",
                        type("S", (), {"live_trading_enabled": True})())
    monkeypatch.setattr("app.trading.live_trader.any_active", lambda: False)

    from app.trading.live_trader import execute_live_order
    result = execute_live_order(
        token_id="123", side="BUY", price=0.4, size_usd=10.0,
        keystore_path="/fake", passphrase="fake",
        confirmed_checklist=[],   # nothing confirmed
    )
    assert result["success"] is False
    assert "checklist" in result["reason"].lower()


def test_live_order_blocked_by_kill_switch(monkeypatch):
    monkeypatch.setattr("app.trading.live_trader.settings",
                        type("S", (), {"live_trading_enabled": True})())
    monkeypatch.setattr("app.trading.live_trader.any_active", lambda: True)

    from app.trading.live_trader import execute_live_order
    result = execute_live_order(
        token_id="123", side="BUY", price=0.4, size_usd=10.0,
        keystore_path="/fake", passphrase="fake",
        confirmed_checklist=CHECKLIST_ITEMS,
    )
    assert result["success"] is False
    assert "kill switch" in result["reason"].lower()


def test_live_order_blocked_when_disabled(monkeypatch):
    monkeypatch.setattr("app.trading.live_trader.settings",
                        type("S", (), {"live_trading_enabled": False})())
    monkeypatch.setattr("app.trading.live_trader.any_active", lambda: False)

    from app.trading.live_trader import execute_live_order
    result = execute_live_order(
        token_id="123", side="BUY", price=0.4, size_usd=10.0,
        keystore_path="/fake", passphrase="fake",
        confirmed_checklist=CHECKLIST_ITEMS,
    )
    assert result["success"] is False
    assert "LIVE_TRADING_ENABLED" in result["reason"]


# ── Emergency shutdown ────────────────────────────────────────────────────────

def test_emergency_shutdown_trips_kill_switches(monkeypatch):
    # Mock cancel_all_orders to avoid HTTP call
    monkeypatch.setattr(
        "app.polymarket.execution.settings",
        type("S", (), {"live_trading_enabled": False})()
    )
    from app.risk.kill_switch import _switches, reset

    # Reset first
    _switches["live_trading"] = False
    _switches["manual"] = False

    result = emergency_shutdown(reason="test shutdown")
    assert result["shutdown"] is True
    assert _switches["live_trading"] is True
    assert _switches["manual"] is True

    # Cleanup
    _switches["live_trading"] = False
    _switches["manual"] = False


# ── Reconciler ───────────────────────────────────────────────────────────────

def test_reconciler_ghost_detection(tmp_path, monkeypatch):
    import app.database as db_module
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(f"sqlite:///{tmp_path}/rec.db",
                           connect_args={"check_same_thread": False})
    db_module.Base.metadata.create_all(engine)
    db_module.engine = engine
    db_module.SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    # Mock on-chain: one position not in local DB
    monkeypatch.setattr(
        "app.polymarket.execution.get_positions",
        lambda addr: [{"conditionId": "mkt-onchain-only", "size": "10"}]
    )

    from app.trading.reconciler import reconcile
    report = reconcile("0xFakeAddress")

    assert "mkt-onchain-only" in report["ghost_positions"]
    assert report["status"] == "MISMATCH"
    assert report["action_required"] is True


def test_reconciler_phantom_detection(tmp_path, monkeypatch):
    import app.database as db_module
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from datetime import datetime, timezone
    import uuid

    engine = create_engine(f"sqlite:///{tmp_path}/rec2.db",
                           connect_args={"check_same_thread": False})
    db_module.Base.metadata.create_all(engine)
    db_module.engine = engine
    db_module.SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    # Insert local open trade
    from app.database import PaperTrade, get_session
    t = PaperTrade(
        trade_id=str(uuid.uuid4())[:12], signal_id="s1",
        market_id="mkt-local-only", market_question="test",
        market_type="A", strategy_name="test",
        entry_time=datetime.now(timezone.utc),
        entry_price=0.4, side="YES", size=10.0,
        model_probability_at_entry=0.6, market_probability_at_entry=0.4,
        edge_at_entry=0.2, resolution_source_match_score=1.0, status="OPEN",
    )
    with get_session() as s:
        s.add(t)

    # Mock on-chain: empty (position not on-chain)
    monkeypatch.setattr(
        "app.polymarket.execution.get_positions", lambda addr: []
    )

    from app.trading.reconciler import reconcile
    from app.risk.kill_switch import _switches
    _switches["live_trading"] = False  # reset before test

    report = reconcile("0xFakeAddress")
    assert "mkt-local-only" in report["phantom_positions"]
    assert report["status"] == "CRITICAL_MISMATCH"
    assert _switches["live_trading"] is True  # kill switch tripped

    _switches["live_trading"] = False  # cleanup
