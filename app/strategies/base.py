"""Base strategy interface."""
from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    @abstractmethod
    def generate_signal(self, market: dict, prices: dict) -> dict | None:
        """Return a signal dict or None if no opportunity."""
