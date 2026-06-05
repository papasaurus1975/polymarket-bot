"""Unit tests for market type classifier."""
from app.ai.market_classifier import classify_market


def test_type_a_price_barrier():
    market = {"question": "Will BTC be above $100,000 by Friday?"}
    assert classify_market(market) == "A"


def test_type_b_regulatory():
    market = {"question": "Will the SEC approve a spot ETH ETF in Q3?"}
    assert classify_market(market) == "B"


def test_type_c_relative():
    market = {"question": "Will ETH outperform BTC this month?"}
    assert classify_market(market) == "C"


def test_type_d_ambiguous():
    market = {"question": "Will crypto sentiment be bullish by year end?"}
    assert classify_market(market) == "D"
