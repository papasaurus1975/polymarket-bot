"""Signal explanation engine and confidence scoring.

Generates plain-English rationale for each signal.
"""
import structlog
from app.risk.kill_switch import is_active

log = structlog.get_logger()


def explain_signal(signal, news_items: list[dict] | None = None,
                   events: list[dict] | None = None) -> str:
    """
    Generate a plain-English explanation for a signal.
    Uses OpenAI if available, otherwise builds a rule-based explanation.
    """
    if _ai_available():
        return _explain_with_openai(signal, news_items, events)
    return _explain_rule_based(signal, news_items, events)


def _explain_rule_based(signal, news_items, events) -> str:
    side = signal.recommended_side
    edge = signal.estimated_edge
    mtype = signal.market_type
    model_p = signal.model_fair_probability
    market_p = signal.polymarket_price

    lines = [
        f"**{side} signal** on '{signal.market_question[:70]}'",
        f"Model estimates {model_p:.0%} probability vs market price of {market_p:.0%} — edge of {edge:+.0%}.",
    ]

    if mtype == "A":
        lines.append(f"Price-barrier model (lognormal): {signal.reason_for_signal}")
    elif mtype == "B":
        lines.append(f"Bayesian base-rate model: {signal.reason_for_signal}")

    if news_items:
        relevant = [n for n in news_items if n.get("sentiment_score") is not None][:3]
        if relevant:
            lines.append(f"Recent news ({len(relevant)} items): " +
                         "; ".join(n["title"][:60] for n in relevant))

    if events:
        lines.append(f"Upcoming events: " +
                     ", ".join(f"{e['description']} in {e['days_away']}d" for e in events[:2]))

    if signal.resolution_source_match_score < 1.0:
        lines.append(f"⚠️ Resolution source match: {signal.resolution_source_match_score:.1f} — confidence discounted.")

    lines.append(f"Invalidating: {signal.invalidating_conditions}")
    return " | ".join(lines)


def _explain_with_openai(signal, news_items, events) -> str:
    try:
        from openai import OpenAI
        from app.config import settings
        client = OpenAI(api_key=settings.openai_api_key)

        news_str = ""
        if news_items:
            news_str = "\nRecent news:\n" + "\n".join(
                f"- {n['title'][:80]} (sentiment: {n.get('sentiment_score', 'n/a')})"
                for n in news_items[:5]
            )

        events_str = ""
        if events:
            events_str = "\nUpcoming events:\n" + "\n".join(
                f"- {e['description']} in {e['days_away']} days"
                for e in events[:3]
            )

        prompt = f"""Write a concise plain-English rationale (2-3 sentences) for this prediction market signal:

Market: {signal.market_question}
Signal: {signal.recommended_side} | Edge: {signal.estimated_edge:+.1%} | Model: {signal.model_fair_probability:.0%} vs Market: {signal.polymarket_price:.0%}
Model type: {'Lognormal price model' if signal.market_type == 'A' else 'Bayesian model'}
Details: {signal.reason_for_signal}
{news_str}{events_str}

Be specific about why the edge exists. Keep it under 100 words."""

        resp = client.chat.completions.create(
            model="claude-haiku-4-5-20251001",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        log.warning("ai_explain_failed", error=str(e))
        return _explain_rule_based(signal, news_items, events)


def score_signal(signal) -> float:
    """Rule-based confidence score (0.0–1.0)."""
    edge = abs(signal.estimated_edge)
    liquidity = signal.liquidity_score
    resolution = signal.resolution_source_match_score
    return round((edge * 0.5) + (liquidity * 0.3) + (resolution * 0.2), 4)


def _ai_available() -> bool:
    if is_active("ai"):
        return False
    try:
        from app.config import settings
        return bool(settings.ai_scoring_enabled and settings.openai_api_key)
    except Exception:
        return False
