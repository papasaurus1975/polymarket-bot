"""Main research scanner: fetch markets → classify → model → score → signal."""
from datetime import datetime, timezone
import structlog

from app.polymarket.markets import fetch_crypto_markets
from app.polymarket.resolution import parse_resolution_source, score_resolution_match
from app.ai.market_classifier import classify_market
from app.data.crypto_prices import get_price
from app.data.volatility import get_realized_vol
from app.strategies.crypto_probability import (
    type_a_probability, type_b_probability,
    extract_symbol, extract_target_price,
)
from app.trading.signal import build_signal, Signal
from app.risk.kill_switch import any_active

log = structlog.get_logger()

# Base rates for Type B (regulatory/news) markets — tuned over time
TYPE_B_BASE_RATES = {
    "etf": 0.55,
    "approve": 0.40,
    "ban": 0.20,
    "default": 0.35,
}


def _days_until(end_date_str: str) -> float:
    if not end_date_str:
        return 30.0
    try:
        # Normalize: strip time if present, parse as date
        date_part = end_date_str[:10]
        from datetime import date
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


def scan(limit: int = 200, bankroll: float = 1000.0) -> list[Signal]:
    """Run a full research scan. Returns list of signals sorted by edge."""
    if any_active():
        log.warning("scan_blocked_by_kill_switch")
        return []

    log.info("scan_started", limit=limit)
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
            market.get("resolution_source", ""),
            market.get("description", ""),
        )
        res_score = score_resolution_match(res)
        days = _days_until(market.get("end_date", ""))

        model_prob = None
        reason = ""
        ci = (0.0, 1.0)

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
                model_prob = type_a_probability(spot, target, days, vol)
                half_ci = 0.05 + vol * 0.05
                ci = (max(0, model_prob - half_ci), min(1, model_prob + half_ci))
                reason = (
                    f"{symbol} spot=${spot:,.0f}, target=${target:,.0f}, "
                    f"days={days:.0f}, vol={vol:.0%}"
                )

        elif mtype == "B":
            base_rate = _type_b_base_rate(question)
            model_prob = type_b_probability(base_rate, 0.0, days)
            ci = (max(0, model_prob - 0.15), min(1, model_prob + 0.15))
            reason = f"Bayesian base_rate={base_rate}, days={days:.0f}"

        if model_prob is None:
            continue

        sig = build_signal(
            market=market,
            market_type=mtype,
            model_fair_probability=model_prob,
            resolution_source_match_score=res_score,
            reason=reason,
            confidence_interval=ci,
            bankroll=bankroll,
        )
        if sig:
            signals.append(sig)
            log.info(
                "signal_generated",
                id=sig.signal_id,
                question=question[:60],
                type=mtype,
                side=sig.recommended_side,
                edge=sig.estimated_edge,
                confidence=sig.confidence_score,
            )

    signals.sort(key=lambda s: abs(s.estimated_edge), reverse=True)
    log.info("scan_complete", signals_found=len(signals), markets_scanned=len(markets))
    return signals
