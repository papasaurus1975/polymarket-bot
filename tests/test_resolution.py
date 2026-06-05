"""Unit tests for resolution source parser."""
from app.polymarket.resolution import parse_resolution_source, score_resolution_match


def test_parse_coingecko():
    desc = "Resolves based on CoinGecko closing price at UTC midnight."
    result = parse_resolution_source(desc)
    assert result["resolution_source"] == "coingecko"


def test_score_exact_match():
    parsed = {"resolution_source": "binance", "resolution_metric": "last_trade"}
    score = score_resolution_match(parsed, available_feeds=["binance"])
    assert score == 1.0


def test_score_no_match():
    parsed = {"resolution_source": "unknown"}
    score = score_resolution_match(parsed, available_feeds=["binance"])
    assert score == 0.0
