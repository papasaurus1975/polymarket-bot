"""Unit tests for risk limit enforcement."""
from app.risk.limits import check_position_size, check_spread, check_edge


def test_position_size_ok():
    assert check_position_size(size_usd=10, bankroll=1000) is True


def test_position_size_breach():
    assert check_position_size(size_usd=200, bankroll=1000) is False


def test_spread_ok():
    assert check_spread(0.03) is True


def test_spread_breach():
    assert check_spread(0.10) is False


def test_edge_ok():
    assert check_edge(0.10) is True


def test_edge_insufficient():
    assert check_edge(0.02) is False
