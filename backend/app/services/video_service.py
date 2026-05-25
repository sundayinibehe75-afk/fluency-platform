"""Video service — creates Daily.co video rooms for confirmed bookings.

Functions:
- create_room — creates a Daily.co room and stores the URL on the booking
"""
import logging
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.availability_slot import AvailabilitySlot
from app.models.booking import Booking

logger = logging.getLogger(__name__)

DAILY_API_BASE = "https://api.daily.co/v1"
ROOM_EXPIRY_BUFFER_SECONDS = 1800  # 30 minutes after lesson end


async def create_room(db: AsyncSession, booking_id: uuid.UUID) -> str | None:
    """Create a Daily.co video room for the given booking.

    - Fetches the booking and its associated slot to determine lesson end time
    - POSTs to Daily.co REST API to create a room with expiry = lesson end + 30 min
    - Stores the returned room URL on the booking record
    - Returns the room URL on success, None on failure

    Errors are logged and swallowed so that a Daily.co failure does not
    block the booking confirmation flow.
    """
    # Fetch the booking
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()

    if booking is None:
        logger.error(
            "Cannot create video room: booking not found",
            extra={"booking_id": str(booking_id)},
        )
        return None

    # Fetch the associated slot to get lesson end time
    slot_result = await db.execute(
        select(AvailabilitySlot).where(AvailabilitySlot.id == booking.slot_id)
    )
    slot = slot_result.scalar_one_or_none()

    if slot is None:
        logger.error(
            "Cannot create video room: slot not found",
            extra={"booking_id": str(booking_id), "slot_id": str(booking.slot_id)},
        )
        return None

    # Calculate room expiry: lesson end time + 30 minutes
    lesson_end_unix = int(slot.end_at.timestamp())
    room_exp = lesson_end_unix + ROOM_EXPIRY_BUFFER_SECONDS

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{DAILY_API_BASE}/rooms",
                headers={
                    "Authorization": f"Bearer {settings.daily_api_key}",
                    "Content-Type": "application/json",
                },
                json={"properties": {"exp": room_exp}},
                timeout=10.0,
            )
            response.raise_for_status()

        room_data = response.json()
        room_url = room_data["url"]

        # Store the room URL on the booking
        booking.video_room_url = room_url
        await db.flush()

        logger.info(
            "Video room created successfully",
            extra={
                "booking_id": str(booking_id),
                "room_url": room_url,
                "room_exp": room_exp,
            },
        )

        return room_url

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Daily.co API returned an error",
            extra={
                "booking_id": str(booking_id),
                "status_code": exc.response.status_code,
                "response_body": exc.response.text,
            },
        )
        return None

    except httpx.RequestError as exc:
        logger.error(
            "Failed to connect to Daily.co API",
            extra={
                "booking_id": str(booking_id),
                "error": str(exc),
            },
        )
        return None

    except Exception as exc:
        logger.exception(
            "Unexpected error creating video room",
            extra={"booking_id": str(booking_id)},
        )
        return None
