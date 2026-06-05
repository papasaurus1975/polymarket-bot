"""Signal generation and schema."""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Signal:
    signal_id: str
    timestamp: datetime
    market_id: str
    market_question: str
    sector: str
    market_type: str                        # A / B / C / D
    strategy_name: str
    recommended_side: str                   # YES / NO
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
