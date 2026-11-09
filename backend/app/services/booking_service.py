"""Booking service — business logic for managing lesson bookings.

Functions:
- create_booking — initiate a booking for a student on a slot
- confirm_booking — transition booking to confirmed, mark slot as booked
- cancel_booking — cancel a booking; refund or return the credit with 12h+ notice
- book_weekly — book the same time every week with plan lessons
- reschedule_booking — move a confirmed booking to another slot (12h+ notice)
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
DEFAULT_SINGLE_PRICE_CENTS = 1000  # $10, used only if the price row is missing
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
        "booking_type": booking.booking_type or "single",
        "late_cancellation": bool(booking.late_cancellation),
    }
    return BookingResponse.model_validate(data)


async def create_booking(
    db: AsyncSession,
    student_id: uuid.UUID,
    slot_id: uuid.UUID,
    booking_type: str = "single",
    notify: bool = True,
) -> BookingResponse:
    """Create a new booking for the given student and slot.

    booking_type:
    - "single": paid per lesson. Status pending_payment with a 15-minute
      reservation while the student pays through Stripe.
    - "plan":   uses one credit from the student's monthly plan (or credits
      added by the tutor). Confirmed immediately.
    - "trial":  the student's one free trial lesson. Confirmed immediately.

    Prevents booking unavailable, past or already-booked slots (409).
    """
    if booking_type not in ("single", "plan", "trial"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "detail": "Unknown booking type."},
        )
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

    now = datetime.now(tz=timezone.utc)
    grant = None

    if booking_type == "single":
        price_result = await db.execute(
            select(PriceConfig).where(PriceConfig.product_key == "single_session")
        )
        price_config = price_result.scalar_one_or_none()
        if price_config is None:
            logger.warning("single_session price missing; using the default $10")
            price_cents, currency = DEFAULT_SINGLE_PRICE_CENTS, "USD"
        else:
            price_cents = price_config.price_cents
            currency = price_config.currency
        booking_status = "pending_payment"
        reserved_until = now + timedelta(minutes=RESERVATION_MINUTES)
    else:
        from app.services import credit_service

        if booking_type == "trial":
            if not await credit_service.trial_available(db, student_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error": "TRIAL_USED", "detail": "You have already used your free trial lesson."},
                )
        else:
            grant = await credit_service.find_usable_grant(db, student_id, slot.start_at)
            if grant is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "NO_CREDITS",
                        "detail": "You have no lesson credits valid for this date. "
                                  "Choose a plan or book a single lesson.",
                    },
                )
            grant.used += 1
        price_cents = 0
        currency = "USD"
        booking_status = "confirmed"
        reserved_until = None

    booking = Booking(
        student_id=student_id,
        tutor_id=slot.tutor_id,
        slot_id=slot_id,
        status=booking_status,
        booking_type=booking_type,
        credit_grant_id=grant.id if grant is not None else None,
        price_cents=price_cents,
        currency=currency,
        reserved_until=reserved_until,
    )
    db.add(booking)
    if booking_status == "confirmed":
        slot.status = "booked"
    try:
        await db.flush()
    except IntegrityError:
        # Another student booked the same slot at the same moment; the
        # database's one-active-booking-per-slot rule rejected this one.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "BOOKING_CONFLICT", "detail": "This slot is no longer available."},
        )

    if booking_status == "confirmed":
        # Free trial and plan lessons need no payment: email + video room now
        await notify_booking_confirmed(db, booking.id, send_email=notify)

    return _booking_to_response(booking, slot)


async def notify_booking_confirmed(
    db: AsyncSession, booking_id: uuid.UUID, send_email: bool = True
) -> None:
    """Send the confirmation email and create the video room for a booking.

    Called after a booking becomes confirmed (normally from the Stripe
    webhook). Failures are logged and never raised, so a problem with email or
    video never undoes a confirmed payment.
    """
    from app.core import timefmt
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
        if row is not None and send_email:
            booking, slot, student = row
            send_email_later(
                to=student.email,
                template_name="booking_confirmation",
                context={
                    "first_name": student.first_name,
                    "lesson_date": timefmt.lesson_date(slot.start_at, student.timezone),
                    "lesson_time": timefmt.lesson_time(slot.start_at, student.timezone),
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
) -> dict:
    """Cancel a booking and release its slot.

    Rules:
    - Students can only cancel their own bookings; admins can cancel any.
    - Only pending_payment and confirmed bookings can be cancelled.
    - Students cannot cancel a lesson that has already started.
    - A paid (confirmed) booking is refunded when the admin cancels it, or when
      the student cancels at least CANCELLATION_NOTICE_HOURS before the start.
      With less notice the lesson counts as used and is not refunded.
    - Plan lessons get their credit back on the same terms (12h+ notice, or
      cancelled by the admin). With less notice the credit is used up.
    - A free trial cancelled with less notice counts as used.

    Returns:
        {"refund_issued": bool, "credit_returned": bool}
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

    booking_type = booking.booking_type or "single"
    was_confirmed = booking.status == "confirmed"
    was_paid = was_confirmed and booking_type == "single"
    enough_notice = (
        slot is not None
        and slot.start_at - now >= timedelta(hours=CANCELLATION_NOTICE_HOURS)
    )
    in_time = is_admin or enough_notice
    should_refund = was_paid and in_time

    credit_returned = False
    if was_confirmed and not in_time:
        # Late cancellation: the lesson (or credit, or trial) counts as used
        booking.late_cancellation = True
    elif booking_type == "plan" and was_confirmed:
        from app.services.credit_service import return_credit

        credit_returned = await return_credit(db, booking.credit_grant_id)

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
            "credit_returned": credit_returned,
        },
    )

    # Cancellation email (sent in the background)
    try:
        from app.core.config import settings
        from app.services.notification_service import send_email_later

        student_result = await db.execute(select(User).where(User.id == booking.student_id))
        student = student_result.scalar_one_or_none()
        if student is not None:
            if booking_type == "plan":
                refund_status = (
                    "Your lesson credit has been returned to your plan."
                    if credit_returned
                    else "This lesson was cancelled less than "
                    f"{CANCELLATION_NOTICE_HOURS} hours before the start, so the credit is used."
                )
            elif booking_type == "trial":
                refund_status = (
                    "You can book your free trial again."
                    if in_time
                    else "This free trial was cancelled less than "
                    f"{CANCELLATION_NOTICE_HOURS} hours before the start, so it counts as used."
                )
            elif refunded:
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

    return {"refund_issued": refunded, "credit_returned": credit_returned}


async def reschedule_booking(
    db: AsyncSession,
    booking_id: uuid.UUID,
    new_slot_id: uuid.UUID,
    actor: User,
) -> BookingResponse:
    """Move a confirmed booking to another available slot.

    Rules:
    - Students can only move their own bookings; admins can move any.
    - Only confirmed bookings can be moved.
    - Students must reschedule at least CANCELLATION_NOTICE_HOURS before the
      current lesson starts. With less notice it is no longer possible.
    - The new slot must be available and in the future.
    - A plan lesson's credit must still be valid on the new date; if not,
      another valid grant is used, otherwise the move is refused.
    """
    result = await db.execute(select(Booking).where(Booking.id == booking_id).with_for_update())
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

    if booking.status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "detail": "Only confirmed lessons can be rescheduled."},
        )

    old_slot = (
        await db.execute(select(AvailabilitySlot).where(AvailabilitySlot.id == booking.slot_id))
    ).scalar_one_or_none()
    now = datetime.now(tz=timezone.utc)
    if (
        not is_admin
        and old_slot is not None
        and old_slot.start_at - now < timedelta(hours=CANCELLATION_NOTICE_HOURS)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "TOO_LATE",
                "detail": f"Lessons can only be rescheduled at least {CANCELLATION_NOTICE_HOURS} "
                          "hours before they start.",
            },
        )

    if new_slot_id == booking.slot_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "detail": "Choose a different time."},
        )

    new_slot = (
        await db.execute(
            select(AvailabilitySlot).where(AvailabilitySlot.id == new_slot_id).with_for_update()
        )
    ).scalar_one_or_none()
    if new_slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Slot not found."},
        )
    if new_slot.status != "available" or new_slot.start_at <= now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "BOOKING_CONFLICT", "detail": "This slot is no longer available."},
        )
    taken = (
        await db.execute(
            select(Booking.id).where(
                Booking.slot_id == new_slot_id, Booking.status.in_(ACTIVE_STATUSES)
            )
        )
    ).first()
    if taken is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "BOOKING_CONFLICT", "detail": "This slot is no longer available."},
        )

    # Plan lessons: the credit must still be valid on the new date
    if booking.booking_type == "plan" and booking.credit_grant_id is not None:
        from app.models.credit_grant import CreditGrant
        from app.services import credit_service

        grant = (
            await db.execute(select(CreditGrant).where(CreditGrant.id == booking.credit_grant_id))
        ).scalar_one_or_none()
        if grant is None or grant.expires_at <= new_slot.start_at:
            other = await credit_service.find_usable_grant(db, booking.student_id, new_slot.start_at)
            if other is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "CREDIT_EXPIRES",
                        "detail": "Your lesson credit expires before that date. "
                                  "Please choose an earlier time.",
                    },
                )
            other.used += 1
            if grant is not None and grant.used > 0:
                grant.used -= 1
            booking.credit_grant_id = other.id

    if old_slot is not None and old_slot.status == "booked":
        old_slot.status = "available"
    booking.slot_id = new_slot.id
    booking.video_room_url = None
    new_slot.status = "booked"
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "BOOKING_CONFLICT", "detail": "This slot is no longer available."},
        )

    logger.info(
        "Booking rescheduled",
        extra={"booking_id": str(booking.id), "actor_id": str(actor.id), "new_slot_id": str(new_slot.id)},
    )
    # New confirmation email with the new time, and a new video room
    await notify_booking_confirmed(db, booking.id)
    await db.refresh(booking)
    return _booking_to_response(booking, new_slot)


MAX_WEEKLY_LESSONS = 8


async def book_weekly(
    db: AsyncSession,
    student: User,
    slot_id: uuid.UUID,
) -> dict:
    """Book the same weekday and time every week with plan credits.

    Starts with the chosen slot and repeats every 7 days while the student
    has plan lessons that are valid on that date (so it stops when this
    month's lessons run out or expire). Weeks where the tutor has no free
    slot at that time are skipped and reported.

    Returns {"booked": [BookingResponse...], "skipped": [datetime...]}.
    """
    from app.core import timefmt
    from app.core.config import settings
    from app.models.credit_grant import CreditGrant
    from app.services.notification_service import send_email_later

    first = (
        await db.execute(select(AvailabilitySlot).where(AvailabilitySlot.id == slot_id))
    ).scalar_one_or_none()
    if first is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Slot not found."},
        )

    # Book no further than the latest date any of the student's credits are valid
    last_expiry = (
        await db.execute(
            select(CreditGrant.expires_at)
            .where(
                CreditGrant.student_id == student.id,
                CreditGrant.used < CreditGrant.total,
                CreditGrant.expires_at > datetime.now(tz=timezone.utc),
            )
            .order_by(CreditGrant.expires_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if last_expiry is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "NO_CREDITS", "detail": "You have no plan lessons left to book."},
        )

    booked: list[BookingResponse] = []
    skipped: list[datetime] = []
    for week in range(MAX_WEEKLY_LESSONS):
        start_at = first.start_at + timedelta(weeks=week)
        if start_at >= last_expiry:
            break
        slot = (
            await db.execute(
                select(AvailabilitySlot)
                .where(
                    AvailabilitySlot.tutor_id == first.tutor_id,
                    # same time each week (a minute either way is fine)
                    AvailabilitySlot.start_at >= start_at - timedelta(minutes=1),
                    AvailabilitySlot.start_at <= start_at + timedelta(minutes=1),
                    AvailabilitySlot.status == "available",
                )
                .order_by(AvailabilitySlot.start_at)
                .limit(1)
            )
        ).scalar_one_or_none()
        if slot is None:
            skipped.append(start_at)
            continue
        try:
            async with db.begin_nested():
                booked.append(
                    await create_booking(db, student.id, slot.id, "plan", notify=False)
                )
        except HTTPException as exc:
            if isinstance(exc.detail, dict) and exc.detail.get("error") == "NO_CREDITS":
                break  # all lessons used
            skipped.append(start_at)

    if not booked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "BOOKING_CONFLICT", "detail": "None of these times could be booked."},
        )

    try:
        items = "".join(
            f"<p style=\"margin: 0 0 6px;\">{timefmt.lesson_date(b.start_at, student.timezone)}, "
            f"{timefmt.lesson_time(b.start_at, student.timezone)}</p>"
            for b in booked
        )
        skipped_text = (
            "These weeks had no free slot at that time, so they were not booked: "
            + "; ".join(timefmt.short_datetime(d, student.timezone) for d in skipped)
            + ". You can choose another time for them."
            if skipped
            else "You will get a reminder the day before each lesson."
        )
        send_email_later(
            to=student.email,
            template_name="weekly_confirmation",
            context={
                "first_name": student.first_name,
                "lesson_list": items,
                "skipped_text": skipped_text,
                "dashboard_url": f"{settings.frontend_url}/dashboard",
            },
        )
    except Exception:
        logger.exception("Failed to send weekly booking email", extra={"student_id": str(student.id)})

    return {"booked": booked, "skipped": skipped}


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
    from app.models.lesson_note import LessonNote
    from app.models.review import Review

    query = (
        select(Booking, AvailabilitySlot, Review.id, User.first_name, User.last_name, LessonNote.id)
        .join(AvailabilitySlot, Booking.slot_id == AvailabilitySlot.id)
        .join(User, Booking.student_id == User.id)
        .outerjoin(Review, Review.booking_id == Booking.id)
        .outerjoin(LessonNote, LessonNote.booking_id == Booking.id)
    )

    if user.role != "admin":
        query = query.where(Booking.student_id == user.id)

    query = query.order_by(AvailabilitySlot.start_at.desc())

    result = await db.execute(query)
    rows = result.all()
    responses = []
    for booking, slot, review_id, first_name, last_name, note_id in rows:
        response = _booking_to_response(booking, slot, has_review=review_id is not None)
        response.student_name = f"{first_name} {last_name}".strip()
        response.has_notes = note_id is not None
        responses.append(response)
    return responses


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
