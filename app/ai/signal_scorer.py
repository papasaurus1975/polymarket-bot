"""Confidence scoring for signals. Phase 4+ adds AI scoring layer."""


def score_signal(signal: dict) -> float:
    """Rule-based confidence score (0.0–1.0). AI layer added in Phase 4."""
    edge = signal.get("estimated_edge", 0.0)
    liquidity = signal.get("liquidity_score", 0.0)
    resolution = signal.get("resolution_source_match_score", 0.0)
    return round((edge * 0.5) + (liquidity * 0.3) + (resolution * 0.2), 4)
