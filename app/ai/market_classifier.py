"""Market type classification: Type A (barrier), B (regulatory), C (range), D (ambiguous)."""
import re

TYPE_A_PATTERNS = [r"\$[\d,]+", r"above", r"below", r"reach", r"exceed", r"price"]
TYPE_B_PATTERNS = [r"approve", r"sec", r"regulation", r"etf", r"ban", r"law", r"decision"]
TYPE_C_PATTERNS = [r"outperform", r"vs", r"versus", r"more than", r"relative"]


def classify_market(market: dict) -> str:
    """Return market type: 'A', 'B', 'C', or 'D'."""
    question = market.get("question", "").lower()

    if any(re.search(p, question) for p in TYPE_A_PATTERNS):
        return "A"
    if any(re.search(p, question) for p in TYPE_B_PATTERNS):
        return "B"
    if any(re.search(p, question) for p in TYPE_C_PATTERNS):
        return "C"
    return "D"
