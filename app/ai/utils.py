"""Shared AI utilities — import from here, not redefined per module."""
from app.risk.kill_switch import is_active


def ai_available() -> bool:
    """Return True if the AI layer is enabled and configured."""
    if is_active("ai"):
        return False
    try:
        from app.config import settings
        return bool(settings.ai_scoring_enabled and settings.openai_api_key)
    except Exception:
        return False
