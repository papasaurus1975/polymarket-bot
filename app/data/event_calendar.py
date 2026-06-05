"""Scheduled crypto events tracker (FOMC, ETF decisions, token unlocks, options expiry)."""
from datetime import date, timedelta
import structlog

log = structlog.get_logger()

# Static calendar — extended as new events are confirmed
# Each entry: (date, event_type, description, affected_assets, impact_direction, magnitude)
_STATIC_EVENTS = [
    # FOMC meetings 2026
    ("2026-06-17", "FOMC", "Federal Reserve FOMC meeting", ["BTC", "ETH"], "uncertain", 0.6),
    ("2026-07-29", "FOMC", "Federal Reserve FOMC meeting", ["BTC", "ETH"], "uncertain", 0.6),
    ("2026-09-16", "FOMC", "Federal Reserve FOMC meeting", ["BTC", "ETH"], "uncertain", 0.6),
    ("2026-11-04", "FOMC", "Federal Reserve FOMC meeting", ["BTC", "ETH"], "uncertain", 0.6),
    ("2026-12-16", "FOMC", "Federal Reserve FOMC meeting", ["BTC", "ETH"], "uncertain", 0.6),
    # CME Bitcoin options expiry (last Friday of each month)
    ("2026-06-26", "OPTIONS_EXPIRY", "CME BTC options expiry", ["BTC"], "volatile", 0.5),
    ("2026-07-31", "OPTIONS_EXPIRY", "CME BTC options expiry", ["BTC"], "volatile", 0.5),
    ("2026-08-28", "OPTIONS_EXPIRY", "CME BTC options expiry", ["BTC"], "volatile", 0.5),
]


def get_upcoming_events(days: int = 30, assets: list[str] | None = None) -> list[dict]:
    """Return events in the next N days, optionally filtered by asset."""
    today = date.today()
    cutoff = today + timedelta(days=days)
    results = []
    for row in _STATIC_EVENTS:
        event_date = date.fromisoformat(row[0])
        if today <= event_date <= cutoff:
            affected = row[3]
            if assets and not any(a in affected for a in assets):
                continue
            days_away = (event_date - today).days
            results.append({
                "event_id": f"{row[1]}_{row[0]}",
                "event_type": row[1],
                "event_date": row[0],
                "description": row[2],
                "affected_assets": affected,
                "expected_impact_direction": row[4],
                "expected_impact_magnitude": row[5],
                "days_away": days_away,
                "confirmation_status": "scheduled",
            })
    results.sort(key=lambda e: e["days_away"])
    return results


def get_event_signal(symbol: str, days_ahead: int = 7) -> float:
    """
    Return an event calendar adjustment signal for a given symbol.
    +0.05 if a high-impact bullish event is within days_ahead.
    -0.05 if a high-impact bearish event is within days_ahead.
    0.0 otherwise (uncertain events are treated as 0).
    """
    events = get_upcoming_events(days=days_ahead, assets=[symbol])
    signal = 0.0
    for ev in events:
        mag = ev["expected_impact_magnitude"]
        direction = ev["expected_impact_direction"]
        if direction == "bullish":
            signal += mag * 0.1
        elif direction == "bearish":
            signal -= mag * 0.1
    return round(max(-0.15, min(0.15, signal)), 4)
