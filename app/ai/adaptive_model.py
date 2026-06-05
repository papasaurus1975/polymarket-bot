"""Adaptive scoring system: track performance and recommend weight updates.

All recommendations require human approval before being applied to live/semi_auto settings.
Paper mode may apply them automatically for faster iteration (per the PDF).
"""
import structlog
from app.trading.performance import compute_metrics

log = structlog.get_logger()


def analyze_performance(trades) -> dict:
    """Analyze closed trades and return pattern analysis."""
    metrics = compute_metrics(trades)

    by_type = metrics.get("by_type", {})
    findings = []

    for mtype, stats in by_type.items():
        count = stats["count"]
        wins = stats["wins"]
        if count < 5:
            continue
        win_rate = wins / count
        if win_rate < 0.40:
            findings.append({
                "type": "low_win_rate",
                "market_type": mtype,
                "win_rate": round(win_rate, 3),
                "recommendation": f"Consider increasing MIN_EDGE for Type {mtype} markets",
                "severity": "medium",
            })
        elif win_rate > 0.70:
            findings.append({
                "type": "high_win_rate",
                "market_type": mtype,
                "win_rate": round(win_rate, 3),
                "recommendation": f"Type {mtype} performing well — consider increasing position size",
                "severity": "low",
            })

    brier = metrics.get("brier_score")
    if brier and brier > 0.25:
        findings.append({
            "type": "poor_calibration",
            "brier_score": brier,
            "recommendation": "Model probabilities are poorly calibrated — review vol estimates",
            "severity": "high",
        })

    return {"metrics": metrics, "findings": findings}


def recommend_updates(trades) -> list[dict]:
    """
    Return a list of recommended parameter updates based on performance.
    All require human approval before application (per Section 14 of master prompt).
    """
    analysis = analyze_performance(trades)
    updates = []

    for finding in analysis["findings"]:
        if finding["type"] == "low_win_rate":
            updates.append({
                "parameter_name": f"min_edge_{finding['market_type'].lower()}",
                "current_value": 0.07,
                "recommended_value": 0.10,
                "reason": finding["recommendation"],
                "evidence": finding,
                "status": "PENDING_APPROVAL",
            })
        elif finding["type"] == "poor_calibration":
            updates.append({
                "parameter_name": "vol_adjustment_factor",
                "current_value": 1.0,
                "recommended_value": 1.15,
                "reason": finding["recommendation"],
                "evidence": finding,
                "status": "PENDING_APPROVAL",
            })

    if updates:
        log.info("adaptive_updates_recommended", count=len(updates))
    return updates
