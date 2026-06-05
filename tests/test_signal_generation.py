"""Unit tests for edge calculation and signal generation."""
from app.trading.signal import calculate_edge, build_signal


def _market(yes_price=0.40, liquidity=5000, spread=0.03, res_src="binance"):
    return {
        "id": "test-1",
        "question": "Will BTC hit $100,000?",
        "description": f"Resolves based on {res_src} price.",
        "yes_price": yes_price,
        "liquidity": liquidity,
        "spread": spread,
        "end_date": "2026-12-31T00:00:00Z",
    }


def test_edge_positive():
    assert calculate_edge(0.60, 0.40) == 0.20


def test_edge_negative():
    assert calculate_edge(0.30, 0.50) == -0.20


def test_edge_zero():
    assert calculate_edge(0.50, 0.50) == 0.0


def test_signal_generated_when_edge_sufficient():
    sig = build_signal(_market(yes_price=0.30), "A", 0.55, 1.0, "test reason")
    assert sig is not None
    assert sig.recommended_side == "YES"
    assert sig.estimated_edge == pytest.approx(0.25, abs=0.01)


def test_no_signal_when_edge_below_min():
    sig = build_signal(_market(yes_price=0.48), "A", 0.50, 1.0, "tiny edge")
    assert sig is None  # edge = 0.02 < MIN_EDGE 0.07


def test_no_signal_for_type_d():
    sig = build_signal(_market(), "D", 0.60, 1.0, "ambiguous")
    assert sig is None


def test_no_signal_when_low_liquidity():
    sig = build_signal(_market(liquidity=50), "A", 0.60, 1.0, "illiquid")
    assert sig is None


def test_no_signal_when_res_score_too_low():
    sig = build_signal(_market(), "A", 0.60, 0.1, "bad source match")
    assert sig is None


def test_signal_side_no_when_model_below_market():
    sig = build_signal(_market(yes_price=0.70), "A", 0.40, 1.0, "overpriced YES")
    assert sig is not None
    assert sig.recommended_side == "NO"


import pytest
