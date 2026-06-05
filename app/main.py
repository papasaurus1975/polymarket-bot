"""Entry point. Loads config, checks compliance, starts the scheduler."""
from app.config import settings
from app.compliance import check_compliance


def main():
    check_compliance(settings.app_mode)
    # Scheduler and main loop wired up in later phases


if __name__ == "__main__":
    main()
