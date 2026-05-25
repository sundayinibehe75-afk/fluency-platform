"""Availability slot Pydantic schemas.

- RecurrenceConfig — optional nested schema for recurring slot creation
- SlotCreate — request body for creating availability slots
- SlotResponse — response body for availability slot data
- SlotUpdate — request body for partial slot updates
"""
import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import Field

from app.schemas.base import AppBaseModel


class RecurrenceConfig(AppBaseModel):
    """Optional recurrence configuration for slot creation.

    When provided, the service generates individual slots for each week
    up to `weeks_ahead` weeks.
    """

    pattern: Literal["weekly"] = "weekly"
    weeks_ahead: int = Field(..., ge=1, le=8)


class SlotCreate(AppBaseModel):
    """Request body for creating one or more availability slots."""

    tutor_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    duration_minutes: int = Field(..., gt=0)
    recurrence: Optional[RecurrenceConfig] = None


class SlotResponse(AppBaseModel):
    """Response body representing an availability slot."""

    id: uuid.UUID
    tutor_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    duration_minutes: int
    status: str
    recurrence_group_id: Optional[uuid.UUID] = None
    created_at: datetime


class SlotUpdate(AppBaseModel):
    """Request body for partial slot updates (admin only)."""

    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, gt=0)
