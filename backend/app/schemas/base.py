"""Shared Pydantic base model for all API response schemas.

Provides consistent serialisation behaviour:
- datetime → ISO 8601 UTC string (e.g. "2025-07-15T14:00:00Z")
- monetary integers remain integers (no float coercion)
- snake_case field names throughout
- ORM mode enabled via from_attributes
"""
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer


class AppBaseModel(BaseModel):
    """Base schema that all API response/request models should inherit from."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )

    @field_serializer("*", mode="plain")
    @classmethod
    def _serialize_all(cls, value: Any, info: Any) -> Any:
        """Ensure datetimes are serialised as ISO 8601 UTC strings."""
        if isinstance(value, datetime):
            # Ensure UTC and format with trailing Z
            if value.tzinfo is None:
                # Treat naive datetimes as UTC
                value = value.replace(tzinfo=timezone.utc)
            else:
                value = value.astimezone(timezone.utc)
            return value.strftime("%Y-%m-%dT%H:%M:%SZ")
        return value
