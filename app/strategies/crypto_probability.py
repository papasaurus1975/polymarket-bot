"""Probability models for Type A, B, and C markets per the master prompt (Sections 9.1–9.3)."""
import re
import math
from scipy.stats import norm
import structlog

log = structlog.get_logger()

# ── Type A: Barrier / Price-Level (Lognormal) ──────────────────────────────


def type_a_probability(
    current_price: float,
    target_price: float,
    days_to_expiration: float,
    annualized_vol: float,
    trend_adjustment: float = 0.0,
) -> float:
    """
    P(S_T > K) using lognormal model:
        d2 = (ln(S/K) + (r - 0.5σ²)T) / (σ√T)
        P = N(d2)

    trend_adjustment: momentum factor, e.g. +0.02 for strong uptrend.
    """
    if days_to_expiration <= 0 or annualized_vol <= 0:
        return 0.0

    T = days_to_expiration / 365.0
    r = trend_adjustment
    sigma = annualized_vol

    try:
        d2 = (math.log(current_price / target_price) + (r - 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        prob = norm.cdf(d2)
        return float(round(prob, 4))
    except (ValueError, ZeroDivisionError):
        return 0.0


# ── Type B: Regulatory / News Outcome (Bayesian) ──────────────────────────

def type_b_probability(
    base_rate: float,
    news_sentiment_score: float,
    days_to_expiration: float,
    event_calendar_signal: float = 0.0,
) -> float:
    """
    Bayesian update: prior = base_rate, likelihood from news sentiment.
    news_sentiment_score: -1.0 (very negative) to +1.0 (very positive).
    event_calendar_signal: +0.1 if a scheduled decision date is imminent.
    Returns posterior probability (0.0–1.0).
    """
    if not 0.0 < base_rate < 1.0:
        base_rate = max(0.01, min(0.99, base_rate))

    # Convert sentiment to a likelihood ratio
    sentiment_weight = 0.15
    posterior = base_rate + news_sentiment_score * sentiment_weight + event_calendar_signal

    # Time-decay: uncertainty grows as expiration approaches without resolution
    if days_to_expiration > 0:
        decay = 1.0 - 0.01 * min(days_to_expiration, 30) / 30
        posterior = base_rate + (posterior - base_rate) * decay

    return float(round(max(0.01, min(0.99, posterior)), 4))


# ── Type C: Range / Relative Outcome (Spread model) ───────────────────────

def type_c_probability(
    current_spread: float,
    spread_mean: float,
    spread_std: float,
    threshold: float = 0.0,
) -> float:
    """
    P(spread > threshold) modeled as mean-reverting normal distribution.
    current_spread: e.g. log(ETH/BTC)
    """
    if spread_std <= 0:
        return 0.5
    z = (current_spread - threshold) / spread_std
    return float(round(norm.cdf(z), 4))


# ── Symbol extraction helper ───────────────────────────────────────────────

SYMBOL_PATTERNS = [
    (r"\b(BTC|bitcoin)\b", "BTC"),
    (r"\b(ETH|ethereum)\b", "ETH"),
    (r"\b(SOL|solana)\b", "SOL"),
    (r"\b(XRP|ripple)\b", "XRP"),
    (r"\b(DOGE|dogecoin)\b", "DOGE"),
]

PRICE_PATTERN = re.compile(r"\$([\d,]+(?:\.\d+)?)\s*([kKmMbB]?)\b")


def extract_symbol(question: str) -> str | None:
    for pattern, sym in SYMBOL_PATTERNS:
        if re.search(pattern, question, re.IGNORECASE):
            return sym
    return None


def extract_target_price(question: str) -> float | None:
    """Pull the price barrier out of a Type A question like 'Will BTC hit $100k?'"""
    match = PRICE_PATTERN.search(question)
    if not match:
        return None
    price = float(match.group(1).replace(",", ""))
    suffix = match.group(2).lower()
    if suffix == "k":
        price *= 1_000
    elif suffix == "m":
        price *= 1_000_000
    elif suffix == "b":
        price *= 1_000_000_000
    return price
