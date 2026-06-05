"""Kelly criterion and fixed-fraction position sizing."""


def kelly_size(edge: float, odds: float, bankroll: float, fraction: float = 0.25) -> float:
    """Fractional Kelly. fraction=0.25 is conservative quarter-Kelly."""
    kelly_pct = edge / odds
    return bankroll * kelly_pct * fraction


def fixed_fraction_size(bankroll: float, pct: float) -> float:
    return bankroll * pct
