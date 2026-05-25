"""Scheduled background task — send lesson reminder emails.

This task queries upcoming lessons in the next 24–25 hour window
(confirmed bookings where slot start_at is between now+24h and now+25h)
and sends a reminder email to each student.

Intended to be called periodically (e.g. every hour via a scheduler).
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.availability_slot import AvailabilitySlot
from app.models.booking import Booking
from app.models.user import User
from app.services import notification_service

logger = logging.getLogger(__name__)


async def send_lesson_reminders(db: AsyncSession) -> int:
    """Send 24-hour reminder emails for upcoming confirmed lessons.

    Queries bookings where:
    - status is 'confirmed'
    - the associated slot's start_at is between now+24h and now+25h

    This 1-hour window ensures that when the task runs hourly, each lesson
    gets exactly one reminder (no duplicates, no missed reminders).

    Returns the number of reminders sent.
    """
    now = datetime.now(tz=timezone.utc)
    window_start = now + timedelta(hours=24)
    window_end = now + timedelta(hours=25)

    # Query confirmed bookings with slots starting in the 24-25h window
    result = await db.execute(
        select(Booking)
        .join(AvailabilitySlot, Booking.slot_id == AvailabilitySlot.id)
        .options(
            selectinload(Booking.student),
            selectinload(Booking.slot),
        )
        .where(
            and_(
                Booking.status == "confirmed",
                AvailabilitySlot.start_at >= window_start,
                AvailabilitySlot.start_at < window_end,
            )
        )
    )
    bookings = result.scalars().all()

    sent_count = 0
    for booking in bookings:
        student: User = booking.student
        slot: AvailabilitySlot = booking.slot

        lesson_date = slot.start_at.strftime("%A, %B %d, %Y")
        lesson_time = slot.start_at.strftime("%H:%M UTC")
        lesson_url = f"{settings.frontend_url}/lessons/{booking.id}"

        try:
            await notification_service.send_email(
                to=student.email,
                template_name="lesson_reminder",
                context={
                    "first_name": student.first_name,
                    "lesson_date": lesson_date,
                    "lesson_time": lesson_time,
                    "lesson_url": lesson_url,
                },
            )
            sent_count += 1
            logger.info(
                "Lesson reminder sent",
                extra={
                    "booking_id": str(booking.id),
                    "student_id": str(student.id),
                    "lesson_start": slot.start_at.isoformat(),
                },
            )
        except Exception:
            logger.exception(
                "Failed to send lesson reminder",
                extra={
                    "booking_id": str(booking.id),
                    "student_id": str(student.id),
                },
            )

    logger.info(
        "Lesson reminder task completed",
        extra={"reminders_sent": sent_count, "total_bookings": len(bookings)},
    )
    return sent_count
