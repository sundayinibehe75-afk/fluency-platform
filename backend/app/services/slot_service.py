"""Lesson lengths: carving lessons out of free time, and joining it back.

The tutor's availability is a set of free blocks (slots). A student books a
30- or 60-minute lesson starting on any half hour inside a free block:

    free 10:00-12:00, book 10:30-11:00  ->  free 10:00-10:30
                                            lesson 10:30-11:00
                                            free 11:00-12:00

A booking's times come from its slot, so a slot that a booking points to is
never changed. Carving replaces the free block with new slots, and the old
one is removed (kept with status 'removed' if bookings ever pointed to it,
otherwise deleted). When a lesson is cancelled, its slot becomes free again
and is joined with free neighbours the same way, so a 60-minute lesson can be
booked over two freed half hours.
"""
import logging
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability_slot import AvailabilitySlot
from app.models.booking import Booking

logger = logging.getLogger(__name__)

STEP = timedelta(minutes=30)
LESSON_LENGTHS = (30, 60)
ACTIVE = ("pending_payment", "confirmed")


def check_length(minutes: int) -> None:
    if minutes not in LESSON_LENGTHS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "detail": "Lessons are 30 or 60 minutes."},
        )


def _unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"error": "BOOKING_CONFLICT", "detail": "This time is no longer available. Please choose another."},
    )


def lesson_starts(slot: AvailabilitySlot, minutes: int, after: datetime) -> list[datetime]:
    """Half-hour start times in a free slot where a lesson of `minutes` fits."""
    length = timedelta(minutes=minutes)
    starts, t = [], slot.start_at
    while t + length <= slot.end_at:
        if t > after:
            starts.append(t)
        t += STEP
    return starts


async def has_active_booking(db: AsyncSession, slot_id) -> bool:
    return (
        await db.execute(select(Booking.id).where(Booking.slot_id == slot_id, Booking.status.in_(ACTIVE)).limit(1))
    ).first() is not None


async def _retire(db: AsyncSession, slot: AvailabilitySlot) -> None:
    has_history = (
        await db.execute(select(Booking.id).where(Booking.slot_id == slot.id).limit(1))
    ).first() is not None
    if has_history:
        slot.status = "removed"
    else:
        await db.delete(slot)


def _new(like: AvailabilitySlot, start_at: datetime, end_at: datetime) -> AvailabilitySlot:
    return AvailabilitySlot(
        tutor_id=like.tutor_id,
        start_at=start_at,
        end_at=end_at,
        duration_minutes=int((end_at - start_at).total_seconds() // 60),
        status="available",
        recurrence_group_id=like.recurrence_group_id,
    )


async def carve(db: AsyncSession, slot: AvailabilitySlot, start_at: datetime, minutes: int) -> AvailabilitySlot:
    """Return a free slot that is exactly [start_at, start_at + minutes).

    `slot` must be free, locked by the caller (SELECT ... FOR UPDATE) and
    contain that time on a half-hour step from its start.
    """
    end_at = start_at + timedelta(minutes=minutes)
    if (
        start_at < slot.start_at
        or end_at > slot.end_at
        or (start_at - slot.start_at) % STEP != timedelta(0)
    ):
        raise _unavailable()
    if start_at == slot.start_at and end_at == slot.end_at:
        return slot

    lesson = _new(slot, start_at, end_at)
    pieces = [lesson]
    if slot.start_at < start_at:
        pieces.append(_new(slot, slot.start_at, start_at))
    if end_at < slot.end_at:
        pieces.append(_new(slot, end_at, slot.end_at))
    await _retire(db, slot)
    await db.flush()  # the old block must be gone before the new ones exist
    db.add_all(pieces)
    await db.flush()
    return lesson


async def _free_neighbour(db: AsyncSession, slot: AvailabilitySlot, before: bool) -> AvailabilitySlot | None:
    touching = AvailabilitySlot.end_at == slot.start_at if before else AvailabilitySlot.start_at == slot.end_at
    candidates = await db.execute(
        select(AvailabilitySlot)
        .where(
            and_(
                AvailabilitySlot.tutor_id == slot.tutor_id,
                AvailabilitySlot.status == "available",
                AvailabilitySlot.id != slot.id,
                touching,
            )
        )
        .with_for_update()
    )
    for candidate in candidates.scalars():
        if not await has_active_booking(db, candidate.id):
            return candidate
    return None


async def release(db: AsyncSession, slot: AvailabilitySlot | None) -> AvailabilitySlot | None:
    """Make a slot free again (its booking was cancelled) and join it with
    free neighbouring time. Returns the free slot now covering that time."""
    if slot is None or slot.status == "removed":
        return slot
    slot.status = "available"
    await db.flush()
    if await has_active_booking(db, slot.id):
        return slot

    chain = [slot]
    while (left := await _free_neighbour(db, chain[0], before=True)) is not None:
        chain.insert(0, left)
    while (right := await _free_neighbour(db, chain[-1], before=False)) is not None:
        chain.append(right)
    if len(chain) == 1:
        return slot

    merged = _new(slot, chain[0].start_at, chain[-1].end_at)
    for piece in chain:
        await _retire(db, piece)
    await db.flush()
    db.add(merged)
    await db.flush()
    return merged


async def reclaim(db: AsyncSession, slot: AvailabilitySlot) -> AvailabilitySlot | None:
    """For a payment that arrived after its hold ran out: get the lesson's
    time back if it is still free. Returns the slot to book, or None."""
    if slot.status == "available" and not await has_active_booking(db, slot.id):
        return slot
    if slot.status != "removed":
        return None
    minutes = int((slot.end_at - slot.start_at).total_seconds() // 60)
    containing = await db.execute(
        select(AvailabilitySlot)
        .where(
            and_(
                AvailabilitySlot.tutor_id == slot.tutor_id,
                AvailabilitySlot.status == "available",
                AvailabilitySlot.start_at <= slot.start_at,
                AvailabilitySlot.end_at >= slot.end_at,
            )
        )
        .with_for_update()
    )
    for free in containing.scalars():
        if not await has_active_booking(db, free.id):
            try:
                return await carve(db, free, slot.start_at, minutes)
            except HTTPException:
                return None
    return None
