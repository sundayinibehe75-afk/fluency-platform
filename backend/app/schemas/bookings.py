"""Booking Pydantic schemas.

- BookingCreate — request body for initiating a booking
- BookingResponse — response body for booking data
- BookingCancelRequest — empty body for cancellation (action inferred from endpoint)
"""
import uuid
from datetime import datetime
from typing import Optional

from app.schemas.base import AppBaseModel


class BookingCreate(AppBaseModel):
    """Request body for creating a booking."""

    slot_id: uuid.UUID


class BookingResponse(AppBaseModel):
    """Response body representing a booking."""

    id: uuid.UUID
    student_id: uuid.UUID
    tutor_id: uuid.UUID
    slot_id: uuid.UUID
    status: str
    price_cents: int
    currency: str
    stripe_session_id: Optional[str] = None
    video_room_url: Optional[str] = None
    reserved_until: Optional[datetime] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class BookingCancelRequest(AppBaseModel):
    """Empty request body for booking cancellation.

    The cancellation action is inferred from the endpoint path.
    """

    pass
