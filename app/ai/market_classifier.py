"""Market type classification: Type A (barrier), B (regulatory), C (range), D (ambiguous).

Rule-based primary; OpenAI enhancement when configured.
"""
import re
import structlog
from app.risk.kill_switch import is_active

log = structlog.get_logger()

TYPE_A_PATTERNS = [r"\$[\d,]+", r"\babove\b", r"\bbelow\b", r"\breach\b",
                   r"\bexceed\b", r"\bhit\b.*\$", r"\bprice\b"]
TYPE_B_PATTERNS = [r"\bapprove\b", r"\bsec\b", r"\bregulat", r"\betf\b",
                   r"\bban\b", r"\blaw\b", r"\bdecision\b", r"\bvote\b",
                   r"\belection\b", r"\bcourt\b", r"\brussia\b", r"\bwar\b"]
TYPE_C_PATTERNS = [r"\boutperform\b", r"\bvs\b", r"\bversus\b",
                   r"\bmore than\b", r"\brelative\b", r"\bratio\b"]


def classify_market(market: dict) -> str:
    """Return market type: 'A', 'B', 'C', or 'D'. Uses rule-based logic."""
    question = market.get("question", "").lower()

    if any(re.search(p, question) for p in TYPE_A_PATTERNS):
        return "A"
    if any(re.search(p, question) for p in TYPE_B_PATTERNS):
        return "B"
    if any(re.search(p, question) for p in TYPE_C_PATTERNS):
        return "C"
    return "D"


def classify_market_with_ai(market: dict) -> dict:
    """
    Enhanced classification using OpenAI. Returns dict with:
      type, clarity_score, reason, tradability_flag
    Falls back to rule-based on failure or if AI disabled.
    """
    rule_type = classify_market(market)

    if not _ai_available():
        return {
            "type": rule_type,
            "clarity_score": _rule_clarity(rule_type),
            "reason": "rule-based classification",
            "tradability_flag": rule_type != "D",
        }

    try:
        from openai import OpenAI
        from app.config import settings
        client = OpenAI(api_key=settings.openai_api_key)

        prompt = f"""Classify this Polymarket prediction market question:

"{market.get('question', '')}"

Respond with a JSON object:
{{
  "type": "A" | "B" | "C" | "D",
  "clarity_score": 0.0-1.0,
  "reason": "brief explanation",
  "tradability_flag": true | false
}}

Types:
A = Price/barrier by date (e.g. "Will BTC hit $100k?")
B = Regulatory/news outcome (e.g. "Will SEC approve ETF?")
C = Relative/range outcome (e.g. "Will ETH outperform BTC?")
D = Ambiguous/subjective — cannot model reliably"""

        import json
        resp = client.chat.completions.create(
            model="claude-haiku-4-5-20251001",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0,
        )
        result = json.loads(resp.choices[0].message.content.strip())
        log.debug("ai_classification", question=market.get("question", "")[:50],
                  type=result.get("type"), clarity=result.get("clarity_score"))
        return result
    except Exception as e:
        log.warning("ai_classification_failed", error=str(e))
        return {
            "type": rule_type,
            "clarity_score": _rule_clarity(rule_type),
            "reason": f"rule-based fallback (AI error: {str(e)[:50]})",
            "tradability_flag": rule_type != "D",
        }


def _rule_clarity(mtype: str) -> float:
    return {"A": 0.85, "B": 0.65, "C": 0.70, "D": 0.20}.get(mtype, 0.5)


def _ai_available() -> bool:
    if is_active("ai"):
        return False
    try:
        from app.config import settings
        return bool(settings.ai_scoring_enabled and settings.openai_api_key)
    except Exception:
        return False
