"""Tests for Phase 5: approval queue, Kelly sizing, semi-auto routing."""
import pytest
from datetime import datetime, timezone
from app.risk.position_sizing import kelly_size, fixed_fraction_size
from app.trading.signal import Signal


def _sig(edge=0.20, bankroll=1000.0):
    return Signal(
        signal_id="s1", timestamp=datetime.now(timezone.utc),
        market_id="m1", market_question="Will BTC hit $150k?",
        sector="crypto", market_type="A", strategy_name="test",
        recommended_side="YES", polymarket_price=0.30,
        model_fair_probability=0.50, estimated_edge=edge,
        liquidity_score=0.5, resolution_source_match_score=1.0,
        recommended_position_size=10.0,
        reason_for_signal="test", invalidating_conditions="test",
    )


# ── Kelly sizing ────────────────────────────────────────────────────────────

def test_kelly_positive_edge():
    k = kelly_size(0.20, 1000.0)
    assert k["recommended_size_usd"] > 0
    assert k["recommended_size_usd"] <= 10.0  # capped at 1% of 1000


def test_kelly_zero_edge():
    k = kelly_size(0.0, 1000.0)
    assert k["recommended_size_usd"] == 0.0


def test_kelly_derivation_contains_info():
    k = kelly_size(0.15, 2000.0)
    assert "Kelly" in k["derivation"]
    assert "$" in k["derivation"]


def test_kelly_capped_at_max_position():
    # Even with 100% edge, size should be capped at MAX_POSITION_SIZE_PCT
    k = kelly_size(1.0, 1000.0)
    assert k["recommended_size_usd"] <= 10.0


def test_fixed_fraction():
    size = fixed_fraction_size(1000.0, 0.01)
    assert size == pytest.approx(10.0)


# ── Approval queue ──────────────────────────────────────────────────────────

def test_submit_approve_reject_flow(tmp_path, monkeypatch):
    import app.database as db_module
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(f"sqlite:///{tmp_path}/p5.db",
                           connect_args={"check_same_thread": False})
    db_module.Base.metadata.create_all(engine)
    db_module.engine = engine
    db_module.SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    from app.trading.approval_queue import submit_for_approval, approve, reject, get_pending
    from app.risk.position_sizing import kelly_size

    sig = _sig()
    kelly = kelly_size(sig.estimated_edge, 1000.0)
    req = submit_for_approval(sig, kelly)

    assert req["status"] == "PENDING"
    assert req["recommended_side"] == "YES"
    assert req["estimated_edge"] == pytest.approx(0.20)

    pending = get_pending()
    assert len(pending) == 1

    approved = approve(req["request_id"], reviewed_by="test_user", notes="looks good")
    assert approved["status"] == "APPROVED"
    assert approved["reviewed_by"] == "test_user"

    # Can't approve again
    assert approve(req["request_id"]) is None

    # Submit and reject another
    sig2 = _sig(edge=0.10)
    req2 = submit_for_approval(sig2, kelly_size(sig2.estimated_edge, 1000.0))
    rejected = reject(req2["request_id"], notes="too risky")
    assert rejected["status"] == "REJECTED"

    # Pending queue should now be empty
    assert len(get_pending()) == 0


# ── Semi-auto routing ───────────────────────────────────────────────────────

def test_route_research_mode(monkeypatch):
    monkeypatch.setattr("app.trading.semi_auto.settings",
                        type("S", (), {"app_mode": "research",
                                       "live_trading_enabled": False})())
    from app.trading.semi_auto import route_signal
    result = route_signal(_sig())
    assert result["action"] == "logged"


def test_route_live_mode_blocked(monkeypatch):
    monkeypatch.setattr("app.trading.semi_auto.settings",
                        type("S", (), {"app_mode": "live",
                                       "live_trading_enabled": False})())
    from app.trading.semi_auto import route_signal
    result = route_signal(_sig())
    assert result["action"] == "blocked"
