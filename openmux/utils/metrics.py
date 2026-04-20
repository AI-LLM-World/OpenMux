"""Minimal metrics collection utilities.

This module provides simple in-memory counters for use in tests and in
environments without a full metrics backend. It is intentionally tiny; in
production this should be replaced or extended with Prometheus/Sentry/etc.
"""
from typing import Dict


class Metrics:
    def __init__(self):
        self._counters: Dict[str, int] = {}

    def incr(self, name: str, amt: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + int(amt)

    def get(self, name: str) -> int:
        return self._counters.get(name, 0)

    def snapshot(self) -> Dict[str, int]:
        return dict(self._counters)


# Global singleton for quick usage across the codebase
metrics = Metrics()
