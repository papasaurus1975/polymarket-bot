"""Kelly criterion and fixed-fraction position sizing with full derivation shown."""
from app.config import settings


def kelly_size(edge: float, bankroll: float,
               fraction: float = 0.25) -> dict:
    """
    Fractional Kelly position sizing.

    For a binary bet where:
      p = model probability of winning
      q = 1 - p
      b = odds (1/price - 1 for a limit order near ask)

    Kelly fraction = (p*b - q) / b = edge / b
    We use quarter-Kelly (fraction=0.25) for safety.

    Returns dict with size, derivation, and all inputs shown.
    """
    edge = abs(edge)
    if edge <= 0 or bankroll <= 0:
        return {"recommended_size_usd": 0.0, "kelly_fraction": 0.0,
                "derivation": "Edge=0 or bankroll=0 — no position"}

    # Approximate odds from edge (simplified for binary prediction markets)
    # For a YES position at price p_market: odds b ≈ (1 - p_market) / p_market
    # Kelly % = edge / (1 - p_market) roughly
    # We cap at MAX_POSITION_SIZE_PCT regardless
    full_kelly_pct = min(edge, settings.max_position_size_pct * 4)
    fractional_kelly_pct = full_kelly_pct * fraction
    capped_pct = min(fractional_kelly_pct, settings.max_position_size_pct)

    size_usd = round(bankroll * capped_pct, 2)

    derivation = (
        f"Full Kelly ≈ {full_kelly_pct:.1%} of bankroll | "
        f"Quarter-Kelly = {fractional_kelly_pct:.1%} | "
        f"Capped at MAX_POSITION_SIZE_PCT={settings.max_position_size_pct:.1%} | "
        f"Size = ${size_usd:.2f} on ${bankroll:,.0f} bankroll"
    )

    return {
        "recommended_size_usd": size_usd,
        "kelly_fraction": round(capped_pct, 4),
        "full_kelly_pct": round(full_kelly_pct, 4),
        "fractional_kelly_pct": round(fractional_kelly_pct, 4),
        "derivation": derivation,
    }


def fixed_fraction_size(bankroll: float,
                        pct: float | None = None) -> float:
    pct = pct or settings.max_position_size_pct
    return round(bankroll * pct, 2)
