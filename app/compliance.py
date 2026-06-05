"""Jurisdiction and terms-of-service compliance gate."""


def check_compliance(app_mode: str) -> None:
    """Halt if mode requires compliance approval that hasn't been granted."""
    if app_mode in ("semi_auto", "live"):
        from app.config import settings
        if not settings.compliance_approved:
            raise RuntimeError(
                "COMPLIANCE_APPROVED must be set to true before running "
                f"in {app_mode} mode. Review jurisdictional restrictions first."
            )
