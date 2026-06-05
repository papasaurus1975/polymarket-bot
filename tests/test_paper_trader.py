"""Tests for paper trading engine."""
import pytest
from datetime import datetime, timezone
from app.trading.signal import Signal
from app.trading.paper_trader import simulate_fill, enter_trade, close_trade, get_all_trades
from app.trading.performance import compute_metrics
from app.database import init_db, PaperTrade


def _signal(yes_price=0.30, liquidity_score=0.05, edge=0.25):
    return Signal(
        signal_id="test-sig",
        timestamp=datetime.now(timezone.utc),
        market_id="mkt-001",
        market_question="Will BTC hit $150k by December 31?",
        sector="crypto",
        market_type="A",
        strategy_name="crypto_probability_mispricing",
        recommended_side="YES",
        polymarket_price=yes_price,
        model_fair_probability=yes_price + edge,
        estimated_edge=edge,
        liquidity_score=liquidity_score,
        resolution_source_match_score=1.0,
        recommended_position_size=10.0,
        mode="paper",
    )


def test_simulate_fill_returns_valid_price():
    fill = simulate_fill(_signal())
    assert 0.01 <= fill["actual_price"] <= 0.99
    assert 0.0 < fill["fill_ratio"] <= 1.0
    assert fill["filled_size"] > 0
    assert fill["slippage"] >= 0


def test_simulate_fill_slippage_increases_buy_price():
    sig = _signal(yes_price=0.50, liquidity_score=0.001)  # very illiquid
    fill = simulate_fill(sig)
    # YES buys fill at a higher price (worse for buyer)
    assert fill["actual_price"] >= 0.50


def test_enter_and_close_trade(tmp_path, monkeypatch):
    # Point DB at temp file
    import app.database as db_module
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    test_engine = create_engine(f"sqlite:///{tmp_path}/test.db",
                                connect_args={"check_same_thread": False})
    db_module.Base.metadata.create_all(test_engine)
    db_module.engine = test_engine
    db_module.SessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    trade = enter_trade(_signal())
    assert trade is not None
    assert trade["status"] == "OPEN"
    assert trade["side"] == "YES"

    closed = close_trade(trade["trade_id"], exit_price=0.80, exit_reason="test",
                         final_outcome="YES")
    assert closed is not None
    assert closed["status"] == "CLOSED"
    assert closed["profit_loss"] is not None
    assert closed["model_accuracy"] is True


def test_compute_metrics_empty():
    m = compute_metrics([])
    assert m["total_trades"] == 0
    assert m["total_pnl"] == 0.0


def test_compute_metrics_with_trades(tmp_path, monkeypatch):
    import app.database as db_module
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    test_engine = create_engine(f"sqlite:///{tmp_path}/metrics.db",
                                connect_args={"check_same_thread": False})
    db_module.Base.metadata.create_all(test_engine)
    db_module.engine = test_engine
    db_module.SessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    from app.database import get_session
    from datetime import datetime, timezone
    import uuid

    def insert(pnl, model_prob, outcome):
        t = PaperTrade(
            trade_id=str(uuid.uuid4())[:12],
            signal_id="s1", market_id="m1",
            market_question="test", market_type="A",
            strategy_name="test",
            entry_time=datetime.now(timezone.utc),
            entry_price=0.40, side="YES", size=10.0,
            model_probability_at_entry=model_prob,
            market_probability_at_entry=0.40,
            edge_at_entry=model_prob - 0.40,
            resolution_source_match_score=1.0,
            status="CLOSED",
            profit_loss=pnl,
            final_outcome=outcome,
            calibration_error=abs(model_prob - (1.0 if outcome == "YES" else 0.0)),
        )
        with get_session() as s:
            s.add(t)

    insert(10.0, 0.70, "YES")
    insert(-5.0, 0.60, "NO")
    insert(8.0, 0.65, "YES")

    with db_module.get_session() as s:
        trades = s.query(PaperTrade).all()
        s.expunge_all()

    m = compute_metrics(trades)
    assert m["total_trades"] == 3
    assert m["total_pnl"] == pytest.approx(13.0)
    assert m["win_rate"] == pytest.approx(2 / 3, abs=0.01)
    assert m["brier_score"] is not None
