"""Kill switch logic. Persisted to DB so state survives process restarts.

Per the master prompt: never auto-re-enables after a breach.
Manual reset requires explicit call to reset() with confirmed_by.
"""
import structlog
from datetime import datetime, timezone

log = structlog.get_logger()

VALID_SWITCHES = {
    "daily", "manual", "market", "sector",
    "compliance", "live_trading", "ai",
}


def _load_state() -> dict[str, bool]:
    """Load switch state from DB. Returns all-False dict on first run or DB error."""
    state = {sw: False for sw in VALID_SWITCHES}
    try:
        from app.database import get_session, init_db, AuditLog
        import json
        init_db()
        with get_session() as session:
            # Most recent activation per switch that hasn't been reset
            entries = (
                session.query(AuditLog)
                .filter(AuditLog.event_type.in_(["KILL_SWITCH_ACTIVATED", "KILL_SWITCH_RESET"]))
                .order_by(AuditLog.created_at.asc())
                .all()
            )
            for entry in entries:
                try:
                    data = json.loads(entry.data)
                    sw = data.get("switch")
                    if sw not in VALID_SWITCHES:
                        continue
                    if entry.event_type == "KILL_SWITCH_ACTIVATED":
                        state[sw] = True
                    elif entry.event_type == "KILL_SWITCH_RESET":
                        state[sw] = False
                except Exception:
                    pass
    except Exception as e:
        log.warning("kill_switch_load_failed", error=str(e))
    return state


def _persist(event_type: str, switch: str, reason: str, confirmed_by: str = "system"):
    """Write switch event to AuditLog for persistence across restarts."""
    try:
        from app.database import get_session, init_db, AuditLog
        import json
        init_db()
        entry = AuditLog(
            event_type=event_type,
            data=json.dumps({
                "switch": switch,
                "reason": reason,
                "confirmed_by": confirmed_by,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }),
            created_at=datetime.now(timezone.utc),
        )
        with get_session() as session:
            session.add(entry)
    except Exception as e:
        # Persistence failure must never block the switch itself
        log.error("kill_switch_persist_failed", error=str(e), event_type=event_type)


# In-memory cache — loaded from DB on first access via _get_switches()
_cache: dict[str, bool] | None = None


def _get_switches() -> dict[str, bool]:
    global _cache
    if _cache is None:
        _cache = _load_state()
    return _cache


# Keep _switches as a property-like accessor for backward compatibility
# (dashboard reads `_switches` directly)
class _SwitchProxy:
    def __getitem__(self, key):
        return _get_switches()[key]

    def __setitem__(self, key, value):
        _get_switches()[key] = value

    def __iter__(self):
        return iter(_get_switches())

    def items(self):
        return _get_switches().items()

    def values(self):
        return _get_switches().values()


_switches = _SwitchProxy()


def activate(switch: str, reason: str):
    if switch not in VALID_SWITCHES:
        raise ValueError(f"Unknown kill switch: {switch}")
    _get_switches()[switch] = True
    _persist("KILL_SWITCH_ACTIVATED", switch, reason)
    log.warning("kill_switch_activated", switch=switch, reason=reason)


def is_active(switch: str) -> bool:
    return _get_switches().get(switch, False)


def any_active() -> bool:
    return any(_get_switches().values())


def reset(switch: str, confirmed_by: str):
    """Manual reset only — requires confirmed_by. Never called automatically."""
    if switch not in VALID_SWITCHES:
        raise ValueError(f"Unknown kill switch: {switch}")
    _get_switches()[switch] = False
    _persist("KILL_SWITCH_RESET", switch, reason="manual reset", confirmed_by=confirmed_by)
    log.info("kill_switch_reset", switch=switch, confirmed_by=confirmed_by)
