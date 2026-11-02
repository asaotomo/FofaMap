"""ISO datetime parsing shared by supported Python versions (3.10+)."""

from datetime import datetime


def parse_iso_datetime(value: str) -> datetime:
    # datetime.fromisoformat gained support for the RFC3339 Z suffix in Python 3.11.
    return datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
