"""Unit tests for probability models (Section 9)."""
from app.strategies.crypto_probability import (
    type_a_probability, type_b_probability, type_c_probability,
    extract_symbol, extract_target_price,
)


def test_type_a_above_current():
    # BTC at 60k, target 100k, 30 days, 65% vol → should be < 0.5
    p = type_a_probability(60_000, 100_000, 30, 0.65)
    assert 0.0 < p < 0.5


def test_type_a_below_current():
    # BTC at 60k, target 50k, 30 days → should be > 0.5
    p = type_a_probability(60_000, 50_000, 30, 0.65)
    assert p > 0.5


def test_type_a_expired():
    p = type_a_probability(60_000, 100_000, 0, 0.65)
    assert p == 0.0


def test_type_a_at_target():
    # Price == target → ~50% (slight drift effect)
    p = type_a_probability(100_000, 100_000, 30, 0.65)
    assert 0.3 < p < 0.7


def test_type_b_positive_sentiment():
    p = type_b_probability(0.40, 0.8, 30)
    assert p > 0.40


def test_type_b_negative_sentiment():
    p = type_b_probability(0.40, -0.8, 30)
    assert p < 0.40


def test_type_b_bounds():
    p = type_b_probability(0.50, 5.0, 30)   # extreme sentiment clamped
    assert 0.0 < p <= 1.0


def test_type_c_probability():
    p = type_c_probability(current_spread=0.1, spread_mean=0.0, spread_std=0.05)
    assert p > 0.5


def test_extract_symbol_btc():
    assert extract_symbol("Will BTC hit $100,000?") == "BTC"


def test_extract_symbol_eth():
    assert extract_symbol("Will Ethereum reach $5000?") == "ETH"


def test_extract_symbol_none():
    assert extract_symbol("Will the SEC approve the ETF?") is None


def test_extract_target_price():
    assert extract_target_price("Will BTC hit $100,000?") == 100_000.0


def test_extract_target_price_no_match():
    assert extract_target_price("Will the SEC approve?") is None
