"""Availability service — business logic for managing tutor availability slots.

Functions:
- list_available_slots — returns future available slots for a tutor
- create_slots — creates one or more slots (supports recurrence)
- update_slot — updates a single slot (admin only)
- delete_slot — deletes a slot, cancelling any associated booking
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability_slot import AvailabilitySlot
from app.models.booking import Booking
from app.schemas.availability import SlotCreate, SlotResponse, SlotUpdate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_overlap(
    new_start: datetime,
    new_end: datetime,
    existing_start: datetime,
    existing_end: datetime,
) -> bool:
    """Return True if two time intervals overlap.

    Overlap detection: new_start < existing_end AND new_end > existing_start
    """
    return new_start < existing_end and new_end > existing_start


async def _find_overlapping_slot(
    db: AsyncSession,
    tutor_id: uuid.UUID,
    start_at: datetime,
    end_at: datetime,
    exclude_slot_id: uuid.UUID | None = None,
) -> AvailabilitySlot | None:
    """Query for any existing slot that overlaps the given time range."""
    query = select(AvailabilitySlot).where(
        and_(
            AvailabilitySlot.tutor_id == tutor_id,
            AvailabilitySlot.start_at < end_at,
            AvailabilitySlot.end_at > start_at,
        )
    )
    if exclude_slot_id is not None:
        query = query.where(AvailabilitySlot.id != exclude_slot_id)

    result = await db.execute(query)
    return result.scalar_one_or_none()


def _raise_conflict() -> None:
    """Raise a 409 SLOT_CONFLICT error."""
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"error": "SLOT_CONFLICT", "detail": "The slot overlaps with an existing slot for this tutor."},
    )


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def list_available_slots(
    db: AsyncSession,
    tutor_id: uuid.UUID,
) -> List[SlotResponse]:
    """Return future slots with status 'available' for the given tutor.

    Results are ordered by start_at ASC.
    """
    now = datetime.now(tz=timezone.utc)
    result = await db.execute(
        select(AvailabilitySlot)
        .where(
            and_(
                AvailabilitySlot.tutor_id == tutor_id,
                AvailabilitySlot.status == "available",
                AvailabilitySlot.start_at > now,
            )
        )
        .order_by(AvailabilitySlot.start_at.asc())
    )
    slots = result.scalars().all()
    return [SlotResponse.model_validate(slot) for slot in slots]


async def create_slots(
    db: AsyncSession,
    data: SlotCreate,
) -> List[SlotResponse]:
    """Create one or more availability slots.

    If recurrence is provided, generates individual slots for each week
    up to `weeks_ahead` weeks. Each slot is checked for overlaps with
    existing slots for the same tutor.

    Returns the list of created slots.
    Raises HTTP 409 SLOT_CONFLICT if any slot overlaps.
    """
    slots_to_create: list[dict] = []

    if data.recurrence is not None:
        # Generate recurring slots
        recurrence_group_id = uuid.uuid4()
        weeks = data.recurrence.weeks_ahead
        for week in range(weeks):
            offset = timedelta(weeks=week)
            slot_start = data.start_at + offset
            slot_end = data.end_at + offset
            slots_to_create.append({
                "start_at": slot_start,
                "end_at": slot_end,
                "recurrence_group_id": recurrence_group_id,
            })
    else:
        # Single slot
        slots_to_create.append({
            "start_at": data.start_at,
            "end_at": data.end_at,
            "recurrence_group_id": None,
        })

    # Check for overlaps and create slots
    created_slots: list[AvailabilitySlot] = []
    for slot_data in slots_to_create:
        overlap = await _find_overlapping_slot(
            db,
            tutor_id=data.tutor_id,
            start_at=slot_data["start_at"],
            end_at=slot_data["end_at"],
        )
        if overlap is not None:
            _raise_conflict()

        slot = AvailabilitySlot(
            tutor_id=data.tutor_id,
            start_at=slot_data["start_at"],
            end_at=slot_data["end_at"],
            duration_minutes=data.duration_minutes,
            status="available",
            recurrence_group_id=slot_data["recurrence_group_id"],
        )
        db.add(slot)
        created_slots.append(slot)

    await db.flush()  # Populate IDs and created_at
    return [SlotResponse.model_validate(slot) for slot in created_slots]


async def update_slot(
    db: AsyncSession,
    slot_id: uuid.UUID,
    data: SlotUpdate,
) -> SlotResponse:
    """Update an existing availability slot (admin only).

    Only provided fields are updated. After update, checks for overlaps
    with other slots for the same tutor.

    Raises HTTP 404 if slot not found.
    Raises HTTP 409 SLOT_CONFLICT if updated times overlap another slot.
    """
    result = await db.execute(
        select(AvailabilitySlot).where(AvailabilitySlot.id == slot_id)
    )
    slot = result.scalar_one_or_none()

    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Slot not found."},
        )

    # Apply updates
    if data.start_at is not None:
        slot.start_at = data.start_at
    if data.end_at is not None:
        slot.end_at = data.end_at
    if data.duration_minutes is not None:
        slot.duration_minutes = data.duration_minutes

    # Check for overlaps after update (exclude self)
    overlap = await _find_overlapping_slot(
        db,
        tutor_id=slot.tutor_id,
        start_at=slot.start_at,
        end_at=slot.end_at,
        exclude_slot_id=slot.id,
    )
    if overlap is not None:
        _raise_conflict()

    await db.flush()
    return SlotResponse.model_validate(slot)


async def delete_slot(
    db: AsyncSession,
    slot_id: uuid.UUID,
) -> None:
    """Delete an availability slot.

    If the slot has a confirmed booking, the booking is cancelled
    (status set to 'cancelled'), the slot is released, and a log entry
    is created indicating a notification should be sent.

    Raises HTTP 404 if slot not found.
    """
    result = await db.execute(
        select(AvailabilitySlot).where(AvailabilitySlot.id == slot_id)
    )
    slot = result.scalar_one_or_none()

    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Slot not found."},
        )

    # Check for associated booking
    booking_result = await db.execute(
        select(Booking).where(
            and_(
                Booking.slot_id == slot_id,
                Booking.status.in_(["confirmed", "pending_payment"]),
            )
        )
    )
    booking = booking_result.scalar_one_or_none()

    if booking is not None:
        booking.status = "cancelled"
        logger.info(
            "Booking cancelled due to slot deletion — notification should be sent",
            extra={
                "booking_id": str(booking.id),
                "student_id": str(booking.student_id),
                "slot_id": str(slot_id),
            },
        )

    await db.delete(slot)
    await db.flush()
