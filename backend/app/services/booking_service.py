"""Booking service — business logic for managing lesson bookings.

Functions:
- create_booking — initiate a booking for a student on a slot
- confirm_booking — transition booking to confirmed, mark slot as booked
- cancel_booking — cancel a booking, optionally flag for refund
- get_booking — fetch a single booking with ownership enforcement
- list_bookings — list bookings for a student or all (admin)
- expire_pending_bookings — background task to release expired reservations
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
from app.models.price_config import PriceConfig
from app.models.user import User
from app.schemas.bookings import BookingResponse

logger = logging.getLogger(__name__)

RESERVATION_MINUTES = 15
REFUND_THRESHOLD_HOURS = 24


def _booking_to_response(booking: Booking, slot: AvailabilitySlot | None = None) -> BookingResponse:
    """Convert a Booking ORM object to a BookingResponse, including slot timing."""
    data = {
        "id": booking.id,
        "student_id": booking.student_id,
        "tutor_id": booking.tutor_id,
        "slot_id": booking.slot_id,
        "status": booking.status,
        "price_cents": booking.price_cents,
        "currency": booking.currency,
        "stripe_session_id": booking.stripe_session_id,
        "video_room_url": booking.video_room_url,
        "reserved_until": booking.reserved_until,
        "start_at": slot.start_at if slot else None,
        "end_at": slot.end_at if slot else None,
        "created_at": booking.created_at,
        "updated_at": booking.updated_at,
    }
    return BookingResponse.model_validate(data)


async def create_booking(
    db: AsyncSession,
    student_id: uuid.UUID,
    slot_id: uuid.UUID,
) -> BookingResponse:
    """Create a new booking for the given student and slot.

    - Verifies the slot exists and is available
    - Prevents duplicate bookings (409 BOOKING_CONFLICT)
    - Looks up price from price_configs (product_key = "single_session")
    - Sets status to pending_payment with a 15-minute reservation window
    """
    # Fetch the slot
    result = await db.execute(
        select(AvailabilitySlot).where(AvailabilitySlot.id == slot_id)
    )
    slot = result.scalar_one_or_none()

    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Slot not found."},
        )

    if slot.status != "available":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "BOOKING_CONFLICT", "detail": "This slot is no longer available."},
        )

    # Check for existing booking by this student on this slot
    existing_result = await db.execute(
        select(Booking).where(
            and_(
                Booking.slot_id == slot_id,
                Booking.student_id == student_id,
                Booking.status.in_(["pending_payment", "confirmed"]),
            )
        )
    )
    existing_booking = existing_result.scalar_one_or_none()

    if existing_booking is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "BOOKING_CONFLICT", "detail": "You have already booked this slot."},
        )

    # Also check if any other user has a non-cancelled booking on this slot
    any_booking_result = await db.execute(
        select(Booking).where(
            and_(
                Booking.slot_id == slot_id,
                Booking.status.in_(["pending_payment", "confirmed"]),
            )
        )
    )
    any_existing = any_booking_result.scalar_one_or_none()

    if any_existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "BOOKING_CONFLICT", "detail": "This slot is no longer available."},
        )

    # Look up price from price_configs
    price_result = await db.execute(
        select(PriceConfig).where(PriceConfig.product_key == "single_session")
    )
    price_config = price_result.scalar_one_or_none()

    if price_config is None:
        # Fallback: use a default price if config is missing
        price_cents = 5000  # $50.00 default
        currency = "USD"
    else:
        price_cents = price_config.price_cents
        currency = price_config.currency

    now = datetime.now(tz=timezone.utc)
    reserved_until = now + timedelta(minutes=RESERVATION_MINUTES)

    booking = Booking(
        student_id=student_id,
        tutor_id=slot.tutor_id,
        slot_id=slot_id,
        status="pending_payment",
        price_cents=price_cents,
        currency=currency,
        reserved_until=reserved_until,
    )
    db.add(booking)
    await db.flush()

    return _booking_to_response(booking, slot)


async def confirm_booking(
    db: AsyncSession,
    booking_id: uuid.UUID,
) -> BookingResponse:
    """Confirm a booking: set status to confirmed and mark slot as booked."""
    result = await db.execute(
        select(Booking).where(Booking.id == booking_id)
    )
    booking = result.scalar_one_or_none()

    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Booking not found."},
        )

    booking.status = "confirmed"
    booking.reserved_until = None

    # Update the slot status to booked
    slot_result = await db.execute(
        select(AvailabilitySlot).where(AvailabilitySlot.id == booking.slot_id)
    )
    slot = slot_result.scalar_one_or_none()
    if slot is not None:
        slot.status = "booked"

    await db.flush()

    # Send booking confirmation email (fire-and-forget)
    try:
        from app.services.notification_service import send_email
        from app.core.config import settings

        # Load student for email
        student_result = await db.execute(
            select(User).where(User.id == booking.student_id)
        )
        student = student_result.scalar_one_or_none()

        if student and slot:
            lesson_date = slot.start_at.strftime("%A, %B %d, %Y")
            lesson_time = slot.start_at.strftime("%H:%M UTC")
            lesson_url = f"{settings.frontend_url}/lessons/{booking.id}"

            await send_email(
                to=student.email,
                template_name="booking_confirmation",
                context={
                    "first_name": student.first_name,
                    "lesson_date": lesson_date,
                    "lesson_time": lesson_time,
                    "lesson_url": lesson_url,
                },
            )
    except Exception:
        logger.exception(
            "Failed to send booking confirmation email",
            extra={"booking_id": str(booking_id)},
        )

    # Create video room for the confirmed booking (fire-and-forget)
    try:
        from app.services.video_service import create_room

        await create_room(db, booking.id)
    except Exception:
        logger.exception(
            "Failed to create video room",
            extra={"booking_id": str(booking_id)},
        )

    return _booking_to_response(booking, slot)


async def cancel_booking(
    db: AsyncSession,
    booking_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> bool:
    """Cancel a booking.

    Sets status to cancelled. If the lesson start is more than 24 hours away,
    returns True to flag for refund. Releases the slot back to available.
    Logs a notification entry.

    Returns:
        True if a refund should be issued, False otherwise.
    """
    result = await db.execute(
        select(Booking).where(Booking.id == booking_id)
    )
    booking = result.scalar_one_or_none()

    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Booking not found."},
        )

    booking.status = "cancelled"

    # Release the slot back to available
    slot_result = await db.execute(
        select(AvailabilitySlot).where(AvailabilitySlot.id == booking.slot_id)
    )
    slot = slot_result.scalar_one_or_none()

    should_refund = False
    if slot is not None:
        slot.status = "available"
        # Check if >24h before lesson start
        now = datetime.now(tz=timezone.utc)
        time_until_lesson = slot.start_at - now
        if time_until_lesson > timedelta(hours=REFUND_THRESHOLD_HOURS):
            should_refund = True

    # Log notification
    logger.info(
        "Booking cancelled — notification should be sent",
        extra={
            "booking_id": str(booking_id),
            "actor_id": str(actor_id),
            "student_id": str(booking.student_id),
            "should_refund": should_refund,
        },
    )

    await db.flush()

    # Send cancellation email (fire-and-forget)
    try:
        from app.services.notification_service import send_email
        from app.core.config import settings

        # Load student for email
        student_result = await db.execute(
            select(User).where(User.id == booking.student_id)
        )
        student = student_result.scalar_one_or_none()

        if student:
            # Determine cancellation reason
            if actor_id == booking.student_id:
                reason = "Student-initiated cancellation"
            else:
                reason = "Admin-initiated cancellation"

            refund_status = (
                "A full refund will be issued to your original payment method."
                if should_refund
                else "No refund is applicable for this cancellation."
            )

            await send_email(
                to=student.email,
                template_name="cancellation",
                context={
                    "first_name": student.first_name,
                    "cancellation_reason": reason,
                    "refund_status": refund_status,
                    "frontend_url": settings.frontend_url,
                },
            )
    except Exception:
        logger.exception(
            "Failed to send cancellation email",
            extra={"booking_id": str(booking_id)},
        )

    return should_refund


async def get_booking(
    db: AsyncSession,
    booking_id: uuid.UUID,
    user: User,
) -> BookingResponse:
    """Fetch a single booking with ownership enforcement.

    Students can only see their own bookings. Admins can see all.
    Raises 403 FORBIDDEN if the user is not the owner and not an admin.
    Raises 404 NOT_FOUND if the booking does not exist.
    """
    result = await db.execute(
        select(Booking).where(Booking.id == booking_id)
    )
    booking = result.scalar_one_or_none()

    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Booking not found."},
        )

    # Enforce ownership
    if user.role != "admin" and booking.student_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "FORBIDDEN", "detail": "You do not have access to this booking."},
        )

    # Fetch the associated slot for start/end times
    slot_result = await db.execute(
        select(AvailabilitySlot).where(AvailabilitySlot.id == booking.slot_id)
    )
    slot = slot_result.scalar_one_or_none()

    return _booking_to_response(booking, slot)


async def list_bookings(
    db: AsyncSession,
    user: User,
) -> List[BookingResponse]:
    """List bookings for the current user.

    Students see their own bookings. Admins see all bookings.
    Results are sorted by slot start_at DESC.
    """
    query = select(Booking, AvailabilitySlot).join(
        AvailabilitySlot, Booking.slot_id == AvailabilitySlot.id
    )

    if user.role != "admin":
        query = query.where(Booking.student_id == user.id)

    query = query.order_by(AvailabilitySlot.start_at.desc())

    result = await db.execute(query)
    rows = result.all()
    return [_booking_to_response(booking, slot) for booking, slot in rows]


async def expire_pending_bookings(db: AsyncSession) -> int:
    """Expire pending bookings whose reservation window has passed.

    Finds bookings where status = 'pending_payment' AND reserved_until < now.
    Sets their status to 'cancelled' and releases the associated slots back
    to 'available'.

    Returns the number of expired bookings.
    """
    now = datetime.now(tz=timezone.utc)

    result = await db.execute(
        select(Booking).where(
            and_(
                Booking.status == "pending_payment",
                Booking.reserved_until < now,
            )
        )
    )
    expired_bookings = result.scalars().all()

    count = 0
    for booking in expired_bookings:
        booking.status = "cancelled"

        # Release the slot
        slot_result = await db.execute(
            select(AvailabilitySlot).where(AvailabilitySlot.id == booking.slot_id)
        )
        slot = slot_result.scalar_one_or_none()
        if slot is not None:
            slot.status = "available"

        count += 1
        logger.info(
            "Expired pending booking",
            extra={
                "booking_id": str(booking.id),
                "student_id": str(booking.student_id),
                "slot_id": str(booking.slot_id),
            },
        )

    if count > 0:
        await db.flush()

    return count
