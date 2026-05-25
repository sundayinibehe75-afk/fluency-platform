"""Datetime utility helpers for consistent UTC handling."""
from datetime import datetime, timezone


def to_utc_iso(dt: datetime) -> str:
    """Convert a UTC-aware datetime to an ISO 8601 string ending in 'Z'.

    Args:
        dt: A datetime object. If timezone-aware, it will be converted to UTC.
            If naive, it is assumed to already be in UTC.

    Returns:
        ISO 8601 formatted string, e.g. "2025-07-15T14:00:00Z"
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def from_iso_to_utc(s: str) -> datetime:
    """Parse an ISO 8601 string into a UTC-aware datetime.

    Handles strings ending in 'Z' as well as explicit UTC offsets like '+00:00'.

    Args:
        s: An ISO 8601 datetime string.

    Returns:
        A timezone-aware datetime in UTC.
    """
    # Replace trailing Z with +00:00 for fromisoformat compatibility
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt
