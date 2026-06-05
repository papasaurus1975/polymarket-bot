"""Signal generation, schema, and edge calculation (Section 9.4 + 12)."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from app.config import settings


@dataclass
class Signal:
    signal_id: str
    timestamp: datetime
    market_id: str
    market_question: str
    sector: str
    market_type: str                              # A / B / C / D
    strategy_name: str
    recommended_side: str                         # YES / NO
    polymarket_price: float
    model_fair_probability: float
    model_confidence_interval: tuple[float, float] = (0.0, 1.0)
    estimated_edge: float = 0.0
    confidence_score: float = 0.0
    resolution_source_match_score: float = 0.0
    liquidity_score: float = 0.0
    risk_score: float = 0.0
    recommended_position_size: float = 0.0
    reason_for_signal: str = ""
    invalidating_conditions: str = ""
    news_items_cited: list = field(default_factory=list)
    event_calendar_events_cited: list = field(default_factory=list)
    expiration_time: datetime | None = None
    mode: str = "research"
    status: str = "WATCH"
    ai_score: float | None = None


def calculate_edge(model_prob: float, polymarket_prob: float) -> float:
    """Edge = model fair probability - Polymarket implied probability."""
    return round(model_prob - polymarket_prob, 4)


def build_signal(
    market: dict,
    market_type: str,
    model_fair_probability: float,
    resolution_source_match_score: float,
    reason: str,
    confidence_interval: tuple[float, float] = (0.0, 1.0),
    bankroll: float = 1000.0,
) -> Signal | None:
    """
    Build a Signal if edge >= MIN_EDGE and all quality gates pass.
    Returns None if the market doesn't meet thresholds.
    """
    if market_type == "D":
        return None

    yes_price = market.get("yes_price") or market.get("last_trade_price")
    if yes_price is None:
        return None

    edge = calculate_edge(model_fair_probability, yes_price)
    abs_edge = abs(edge)

    if abs_edge < settings.min_edge:
        return None
    if resolution_source_match_score < settings.min_resolution_source_score:
        return None

    liquidity = market.get("liquidity", 0)
    spread = market.get("spread") or 0
    if liquidity < settings.min_liquidity:
        return None
    if spread > settings.max_spread:
        return None

    side = "YES" if edge > 0 else "NO"
    polymarket_price = yes_price if side == "YES" else (1 - yes_price)

    # Liquidity score: 0–1 scaled to $100k
    liquidity_score = min(liquidity / 100_000, 1.0)

    # Simple confidence: edge * resolution match * liquidity
    confidence_score = round(abs_edge * resolution_source_match_score * liquidity_score, 4)

    # Fixed-fraction sizing (1% of bankroll per the PDF)
    position_size = bankroll * settings.max_position_size_pct

    return Signal(
        signal_id=str(uuid.uuid4())[:8],
        timestamp=datetime.now(timezone.utc),
        market_id=market.get("id", ""),
        market_question=market.get("question", ""),
        sector="crypto",
        market_type=market_type,
        strategy_name="crypto_probability_mispricing",
        recommended_side=side,
        polymarket_price=polymarket_price,
        model_fair_probability=model_fair_probability,
        model_confidence_interval=confidence_interval,
        estimated_edge=edge,
        confidence_score=confidence_score,
        resolution_source_match_score=resolution_source_match_score,
        liquidity_score=liquidity_score,
        recommended_position_size=position_size,
        reason_for_signal=reason,
        invalidating_conditions="Model price feed fails or resolution source changes",
        mode=settings.app_mode,
        status="WATCH",
    )
