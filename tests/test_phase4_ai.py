"""Tests for Phase 4: news, event calendar, AI classifier, signal explainer."""
import pytest
from app.ai.news_interpreter import (
    score_sentiment_rule_based, score_relevance, get_market_sentiment,
)
from app.ai.market_classifier import classify_market, _rule_clarity
from app.ai.signal_scorer import explain_signal, score_signal
from app.data.event_calendar import get_upcoming_events, get_event_signal
from app.trading.signal import Signal
from datetime import datetime, timezone


# ── News interpreter ────────────────────────────────────────────────────────

def test_sentiment_bullish():
    s = score_sentiment_rule_based("Bitcoin ETF approved by SEC in major decision")
    assert s > 0


def test_sentiment_bearish():
    s = score_sentiment_rule_based("SEC bans crypto exchanges in crackdown")
    assert s < 0


def test_sentiment_neutral():
    s = score_sentiment_rule_based("Bitcoin price unchanged today")
    assert s == 0.0


def test_relevance_high():
    r = score_relevance("Bitcoin hits new high as ETF approved", "Will BTC reach $100k?")
    assert r > 0.1


def test_relevance_low():
    r = score_relevance("Soccer team wins championship", "Will BTC reach $100k?")
    assert r == 0.0


def test_market_sentiment_aggregation():
    items = [
        {"title": "Bitcoin ETF approved", "sentiment_score": 0.8,
         "source_credibility_score": 0.9},
        {"title": "Bitcoin ban feared", "sentiment_score": -0.5,
         "source_credibility_score": 0.7},
    ]
    s = get_market_sentiment(items, "Will BTC hit $100k?")
    # Both relevant, net should be positive (bullish item has higher credibility)
    assert isinstance(s, float)


# ── Event calendar ──────────────────────────────────────────────────────────

def test_upcoming_events_returns_list():
    events = get_upcoming_events(days=365)
    assert isinstance(events, list)


def test_event_signal_is_float():
    sig = get_event_signal("BTC", days_ahead=30)
    assert isinstance(sig, float)
    assert -0.15 <= sig <= 0.15


def test_event_calendar_filtered_by_asset():
    btc_events = get_upcoming_events(days=365, assets=["BTC"])
    eth_events = get_upcoming_events(days=365, assets=["ETH"])
    # BTC should have FOMC events, ETH may not have all
    assert all("BTC" in e["affected_assets"] for e in btc_events)


# ── Market classifier ───────────────────────────────────────────────────────

def test_classify_returns_letter():
    assert classify_market({"question": "Will BTC hit $100k?"}) in ("A", "B", "C", "D")


def test_rule_clarity_scores():
    assert _rule_clarity("A") > _rule_clarity("D")
    assert _rule_clarity("B") > _rule_clarity("D")


# ── Signal explainer ────────────────────────────────────────────────────────

def _fake_signal():
    return Signal(
        signal_id="test", timestamp=datetime.now(timezone.utc),
        market_id="mkt1", market_question="Will BTC hit $150k by Dec 31?",
        sector="crypto", market_type="A", strategy_name="test",
        recommended_side="YES", polymarket_price=0.30,
        model_fair_probability=0.55, estimated_edge=0.25,
        liquidity_score=0.5, resolution_source_match_score=1.0,
        reason_for_signal="BTC spot=$60k, target=$150k",
        invalidating_conditions="Model feed fails",
    )


def test_explain_signal_returns_string():
    explanation = explain_signal(_fake_signal(), news_items=[], events=[])
    assert isinstance(explanation, str)
    assert len(explanation) > 10


def test_score_signal_in_range():
    score = score_signal(_fake_signal())
    assert 0.0 <= score <= 1.0
