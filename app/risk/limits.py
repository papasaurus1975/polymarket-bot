"""Hard-coded risk rules. AI must never override these."""
from app.config import settings


def check_position_size(size_usd: float, bankroll: float) -> bool:
    return (size_usd / bankroll) <= settings.max_position_size_pct


def check_daily_loss(daily_loss: float, bankroll: float) -> bool:
    return (daily_loss / bankroll) <= settings.max_daily_loss_pct


def check_spread(spread: float) -> bool:
    return spread <= settings.max_spread


def check_liquidity(liquidity: float) -> bool:
    return liquidity >= settings.min_liquidity


def check_edge(edge: float) -> bool:
    return edge >= settings.min_edge


def check_resolution_source(score: float) -> bool:
    return score >= settings.min_resolution_source_score
