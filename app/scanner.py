"""Main research scanner: fetch → classify → model → news → edge → signal."""
from datetime import datetime, timezone, date
import structlog

from app.polymarket.markets import fetch_crypto_markets
from app.polymarket.resolution import parse_resolution_source, score_resolution_match
from app.ai.market_classifier import classify_market
from app.data.crypto_prices import get_price
from app.data.volatility import get_realized_vol
from app.data.news import fetch_news, get_fear_greed
from app.ai.news_interpreter import enrich_news_with_sentiment
from app.data.event_calendar import get_upcoming_events, get_event_signal
from app.strategies.crypto_probability import (
    type_a_probability, type_b_probability,
    extract_symbol, extract_target_price,
)
from app.ai.news_interpreter import get_market_sentiment
from app.ai.signal_scorer import explain_signal
from app.trading.signal import build_signal, Signal
from app.risk.kill_switch import any_active

log = structlog.get_logger()

TYPE_B_BASE_RATES = {
    "etf": 0.55, "approve": 0.40, "ban": 0.20, "default": 0.35,
}


def _days_until(end_date_str: str) -> float:
    if not end_date_str:
        return 30.0
    try:
        date_part = end_date_str[:10]
        end_date = date.fromisoformat(date_part)
        today = datetime.now(timezone.utc).date()
        return max(0.0, float((end_date - today).days))
    except Exception:
        return 30.0


def _type_b_base_rate(question: str) -> float:
    q = question.lower()
    for kw, rate in TYPE_B_BASE_RATES.items():
        if kw in q:
            return rate
    return TYPE_B_BASE_RATES["default"]


def scan(limit: int = 200, bankroll: float = 1000.0,
         fetch_news_items: bool = True) -> list[Signal]:
    """Full research scan. Returns signals sorted by |edge|."""
    if any_active():
        log.warning("scan_blocked_by_kill_switch")
        return []

    log.info("scan_started", limit=limit)

    # Fetch shared context once
    news_items = []
    fear_greed = {"normalized": 0.0, "value": 50, "classification": "Neutral"}
    if fetch_news_items:
        try:
            raw_news = fetch_news(limit=30)
            news_items = enrich_news_with_sentiment(raw_news)
            fear_greed = get_fear_greed()
            log.info("context_loaded", news=len(news_items),
                     fg=fear_greed["value"], fg_class=fear_greed["classification"])
        except Exception as e:
            log.warning("context_load_failed", error=str(e))

    markets = fetch_crypto_markets(limit=limit)
    signals = []
    price_cache: dict[str, float] = {}
    vol_cache: dict[str, float] = {}

    for market in markets:
        question = market.get("question", "")
        mtype = classify_market(market)
        if mtype == "D":
            continue

        res = parse_resolution_source(
            market.get("resolution_source", ""), market.get("description", ""),
        )
        res_score = score_resolution_match(res)
        days = _days_until(market.get("end_date", ""))

        model_prob = None
        reason = ""
        ci = (0.0, 1.0)
        cited_news = []
        cited_events = []

        if mtype == "A":
            symbol = extract_symbol(question)
            target = extract_target_price(question)
            if symbol and target:
                if symbol not in price_cache:
                    try:
                        price_cache[symbol] = get_price(symbol)
                    except Exception:
                        continue
                if symbol not in vol_cache:
                    vol_cache[symbol] = get_realized_vol(symbol)

                spot = price_cache[symbol]
                vol = vol_cache[symbol]

                # News sentiment adjustment
                sentiment = get_market_sentiment(news_items, question) if news_items else 0.0
                # Fear & Greed adjustment (small)
                fg_adj = fear_greed["normalized"] * 0.02
                # Event calendar signal
                event_signal = get_event_signal(symbol, days_ahead=min(int(days), 30))
                trend = sentiment * 0.03 + fg_adj + event_signal

                model_prob = type_a_probability(spot, target, days, vol, trend_adjustment=trend)
                half_ci = 0.05 + vol * 0.05
                ci = (max(0, model_prob - half_ci), min(1, model_prob + half_ci))
                reason = (f"{symbol} spot=${spot:,.0f}, target=${target:,.0f}, "
                          f"days={days:.0f}, vol={vol:.0%}, "
                          f"sentiment={sentiment:+.2f}, fg={fear_greed['value']}")

                # Cite relevant news
                cited_news = [n for n in news_items
                              if n.get("relevance_score") or
                              symbol.lower() in n.get("title", "").lower()][:3]
                cited_events = get_upcoming_events(days=int(days), assets=[symbol])

        elif mtype == "B":
            base_rate = _type_b_base_rate(question)
            sentiment = get_market_sentiment(news_items, question) if news_items else 0.0
            event_signal = 0.0
            events_near = get_upcoming_events(days=30)
            if events_near:
                cited_events = events_near[:2]
                event_signal = sum(
                    0.05 for e in events_near if e["expected_impact_direction"] != "uncertain"
                )
            model_prob = type_b_probability(base_rate, sentiment, days, event_signal)
            ci = (max(0, model_prob - 0.15), min(1, model_prob + 0.15))
            reason = (f"Bayesian base_rate={base_rate}, "
                      f"sentiment={sentiment:+.2f}, days={days:.0f}")
            cited_news = sorted(
                [n for n in news_items if n.get("sentiment_score") is not None],
                key=lambda n: abs(n.get("sentiment_score", 0)), reverse=True
            )[:3]

        if model_prob is None:
            continue

        sig = build_signal(
            market=market, market_type=mtype,
            model_fair_probability=model_prob,
            resolution_source_match_score=res_score,
            reason=reason, confidence_interval=ci,
            bankroll=bankroll,
        )
        if sig:
            sig.news_items_cited = [n.get("title", "") for n in cited_news]
            sig.event_calendar_events_cited = [e.get("description", "") for e in cited_events]
            # Generate plain-English explanation
            sig.reason_for_signal = explain_signal(sig, cited_news, cited_events)
            signals.append(sig)
            log.info("signal_generated", id=sig.signal_id,
                     question=question[:55], type=mtype,
                     side=sig.recommended_side, edge=sig.estimated_edge)

    signals.sort(key=lambda s: abs(s.estimated_edge), reverse=True)
    log.info("scan_complete", signals=len(signals), markets=len(markets))
    return signals
