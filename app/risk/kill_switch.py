"""Kill switch logic. Never auto-re-enables after a breach."""
import structlog

log = structlog.get_logger()

_switches: dict[str, bool] = {
    "daily": False,
    "manual": False,
    "market": False,
    "sector": False,
    "compliance": False,
    "live_trading": False,
    "ai": False,
}


def activate(switch: str, reason: str):
    if switch not in _switches:
        raise ValueError(f"Unknown kill switch: {switch}")
    _switches[switch] = True
    log.warning("kill_switch_activated", switch=switch, reason=reason)


def is_active(switch: str) -> bool:
    return _switches.get(switch, False)


def any_active() -> bool:
    return any(_switches.values())


def reset(switch: str, confirmed_by: str):
    """Manual reset only — never called automatically."""
    _switches[switch] = False
    log.info("kill_switch_reset", switch=switch, confirmed_by=confirmed_by)
