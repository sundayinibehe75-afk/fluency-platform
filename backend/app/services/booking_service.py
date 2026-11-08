"""Booking service — business logic for managing lesson bookings.

Functions:
- create_booking — initiate a booking for a student on a slot
- confirm_booking — transition booking to confirmed, mark slot as booked
- cancel_booking — cancel a booking, optionally flag for refund
- get_booking — fetch a single booking with ownership enforcement
- list_bookings — list bookings for a student or all (admin)
- expire_pending_bookings — background task to release expired reservations
- complete_finished_bookings — background task to mark past lessons completed
- notify_booking_confirmed — send confirmation email and create the video room
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability_slot import AvailabilitySlot
from app.models.booking import Booking
from app.models.price_config import PriceConfig
from app.models.user import User
from app.schemas.bookings import BookingResponse

logger = logging.getLogger(__name__)

RESERVATION_MINUTES = 15
# Students may cancel (with refund) or reschedule only this many hours before
# the lesson starts. With less notice the lesson counts as used.
CANCELLATION_NOTICE_HOURS = 12
ACTIVE_STATUSES = ("pending_payment", "confirmed")


def _booking_to_response(
    booking: Booking,
    slot: AvailabilitySlot | None = None,
    has_review: bool = False,
) -> BookingResponse:
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
        "has_review": has_review,
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

    if slot.start_at <= datetime.now(tz=timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "BOOKING_CONFLICT", "detail": "This slot has already started."},
        )

    # Check for existing booking by this student on this slot
    existing_result = await db.execute(
        select(Booking).where(
            and_(
                Booking.slot_id == slot_id,
                Booking.student_id == student_id,
                Booking.status.in_(ACTIVE_STATUSES),
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
                Booking.status.in_(ACTIVE_STATUSES),
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
    try:
        await db.flush()
    except IntegrityError:
        # Another student booked the same slot at the same moment; the
        # database's one-active-booking-per-slot rule rejected this one.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "BOOKING_CONFLICT", "detail": "This slot is no longer available."},
        )

    return _booking_to_response(booking, slot)


async def notify_booking_confirmed(db: AsyncSession, booking_id: uuid.UUID) -> None:
    """Send the confirmation email and create the video room for a booking.

    Called after a booking becomes confirmed (normally from the Stripe
    webhook). Failures are logged and never raised, so a problem with email or
    video never undoes a confirmed payment.
    """
    from app.core.config import settings
    from app.services.notification_service import send_email_later
    from app.services.video_service import create_room

    try:
        result = await db.execute(
            select(Booking, AvailabilitySlot, User)
            .join(AvailabilitySlot, Booking.slot_id == AvailabilitySlot.id)
            .join(User, Booking.student_id == User.id)
            .where(Booking.id == booking_id)
        )
        row = result.first()
        if row is not None:
            booking, slot, student = row
            send_email_later(
                to=student.email,
                template_name="booking_confirmation",
                context={
                    "first_name": student.first_name,
                    "lesson_date": slot.start_at.strftime("%A, %B %d, %Y"),
                    "lesson_time": slot.start_at.strftime("%H:%M UTC"),
                    "lesson_url": f"{settings.frontend_url}/lessons/{booking.id}",
                },
            )
    except Exception:
        logger.exception(
            "Failed to send booking confirmation email",
            extra={"booking_id": str(booking_id)},
        )

    try:
        await create_room(db, booking_id)
    except Exception:
        logger.exception(
            "Failed to create video room",
            extra={"booking_id": str(booking_id)},
        )


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
    await db.refresh(booking)
    if slot is not None:
        await db.refresh(slot)

    await notify_booking_confirmed(db, booking.id)

    return _booking_to_response(booking, slot)


async def cancel_booking(
    db: AsyncSession,
    booking_id: uuid.UUID,
    actor: User,
) -> bool:
    """Cancel a booking and release its slot.

    Rules:
    - Students can only cancel their own bookings; admins can cancel any.
    - Only pending_payment and confirmed bookings can be cancelled.
    - Students cannot cancel a lesson that has already started.
    - A paid (confirmed) booking is refunded when the admin cancels it, or when
      the student cancels at least CANCELLATION_NOTICE_HOURS before the start.
      With less notice the lesson counts as used and is not refunded.

    Returns:
        True if a refund was issued, False otherwise.
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

    is_admin = actor.role == "admin"
    if not is_admin and booking.student_id != actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "FORBIDDEN", "detail": "You do not have access to this booking."},
        )

    if booking.status not in ACTIVE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "detail": f"A {booking.status.replace('_', ' ')} booking cannot be cancelled.",
            },
        )

    slot_result = await db.execute(
        select(AvailabilitySlot).where(AvailabilitySlot.id == booking.slot_id)
    )
    slot = slot_result.scalar_one_or_none()

    now = datetime.now(tz=timezone.utc)
    if slot is not None and not is_admin and slot.start_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "detail": "This lesson has already started."},
        )

    was_paid = booking.status == "confirmed"
    enough_notice = (
        slot is not None
        and slot.start_at - now >= timedelta(hours=CANCELLATION_NOTICE_HOURS)
    )
    should_refund = was_paid and (is_admin or enough_notice)

    booking.status = "cancelled"
    booking.reserved_until = None
    if slot is not None and slot.status == "booked":
        slot.status = "available"
    await db.flush()

    refunded = False
    if should_refund:
        try:
            from app.services.payment_service import initiate_refund

            refunded = await initiate_refund(db, booking.id)
        except Exception:
            logger.exception(
                "Refund failed — needs manual follow-up",
                extra={"booking_id": str(booking_id)},
            )

    logger.info(
        "Booking cancelled",
        extra={
            "booking_id": str(booking_id),
            "actor_id": str(actor.id),
            "student_id": str(booking.student_id),
            "refund_issued": refunded,
        },
    )

    # Cancellation email (sent in the background)
    try:
        from app.core.config import settings
        from app.services.notification_service import send_email_later

        student_result = await db.execute(select(User).where(User.id == booking.student_id))
        student = student_result.scalar_one_or_none()
        if student is not None:
            if refunded:
                refund_status = "A full refund has been issued to your original payment method."
            elif should_refund:
                refund_status = "Your refund is being processed and will follow shortly."
            elif was_paid:
                refund_status = (
                    "This lesson was cancelled less than "
                    f"{CANCELLATION_NOTICE_HOURS} hours before the start, so it is not refunded."
                )
            else:
                refund_status = "No payment was taken for this booking."
            send_email_later(
                to=student.email,
                template_name="cancellation",
                context={
                    "first_name": student.first_name,
                    "cancellation_reason": (
                        "Cancelled by the tutor" if is_admin and actor.id != booking.student_id
                        else "Cancelled by you"
                    ),
                    "refund_status": refund_status,
                    "frontend_url": settings.frontend_url,
                },
            )
    except Exception:
        logger.exception(
            "Failed to send cancellation email",
            extra={"booking_id": str(booking_id)},
        )

    return refunded


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
    from app.models.review import Review

    query = (
        select(Booking, AvailabilitySlot, Review.id)
        .join(AvailabilitySlot, Booking.slot_id == AvailabilitySlot.id)
        .outerjoin(Review, Review.booking_id == Booking.id)
    )

    if user.role != "admin":
        query = query.where(Booking.student_id == user.id)

    query = query.order_by(AvailabilitySlot.start_at.desc())

    result = await db.execute(query)
    rows = result.all()
    return [
        _booking_to_response(booking, slot, has_review=review_id is not None)
        for booking, slot, review_id in rows
    ]


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


async def complete_finished_bookings(db: AsyncSession) -> int:
    """Mark confirmed bookings whose lesson has ended as 'completed'.

    Completed bookings are what students can review. Returns the number of
    bookings updated.
    """
    now = datetime.now(tz=timezone.utc)
    result = await db.execute(
        select(Booking)
        .join(AvailabilitySlot, Booking.slot_id == AvailabilitySlot.id)
        .where(
            and_(
                Booking.status == "confirmed",
                AvailabilitySlot.end_at < now,
            )
        )
    )
    finished = result.scalars().all()
    for booking in finished:
        booking.status = "completed"
    if finished:
        await db.flush()
        logger.info("Marked bookings completed", extra={"count": len(finished)})
    return len(finished)
