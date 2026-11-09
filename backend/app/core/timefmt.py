"""Show lesson times in each person's own time zone."""
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones


@lru_cache(maxsize=1)
def _all_zones() -> frozenset[str]:
    return frozenset(available_timezones())


def is_valid_timezone(name: str | None) -> bool:
    return bool(name) and name in _all_zones()


def _zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name) if is_valid_timezone(name) else ZoneInfo("UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def lesson_date(dt: datetime, tz_name: str | None) -> str:
    """e.g. 'Monday, November 9, 2026' in the person's time zone."""
    local = dt.astimezone(_zone(tz_name))
    return f"{local:%A, %B} {local.day}, {local.year}"


def lesson_time(dt: datetime, tz_name: str | None) -> str:
    """e.g. '14:00 (Africa/Lagos)'."""
    zone = _zone(tz_name)
    return f"{dt.astimezone(zone):%H:%M} ({zone.key})"


def short_datetime(dt: datetime, tz_name: str | None) -> str:
    """e.g. 'Mon 9 Nov, 14:00'."""
    local = dt.astimezone(_zone(tz_name))
    return f"{local:%a} {local.day} {local:%b, %H:%M}"
