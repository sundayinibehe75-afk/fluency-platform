"""Lesson notes: the tutor's summary, homework and new words after a lesson."""
import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import timefmt
from app.core.config import settings
from app.models.availability_slot import AvailabilitySlot
from app.models.booking import Booking
from app.models.lesson_note import LessonNote
from app.models.user import User

logger = logging.getLogger(__name__)


def _clean(text: str | None) -> str | None:
    text = (text or "").strip()
    return text or None


def _note_dict(note: LessonNote | None, booking: Booking, slot: AvailabilitySlot) -> dict:
    return {
        "booking_id": booking.id,
        "lesson_start": slot.start_at,
        "booking_type": booking.booking_type,
        "summary": note.summary if note else None,
        "homework": note.homework if note else None,
        "vocabulary": note.vocabulary if note else None,
        "updated_at": note.updated_at if note else None,
    }


async def _load(db: AsyncSession, booking_id: uuid.UUID, user: User):
    row = (
        await db.execute(
            select(Booking, AvailabilitySlot)
            .join(AvailabilitySlot, Booking.slot_id == AvailabilitySlot.id)
            .where(Booking.id == booking_id)
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Lesson not found."},
        )
    booking, slot = row
    if user.role != "admin" and booking.student_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "FORBIDDEN", "detail": "You do not have access to this lesson."},
        )
    note = (
        await db.execute(select(LessonNote).where(LessonNote.booking_id == booking_id))
    ).scalar_one_or_none()
    return booking, slot, note


async def get_notes(db: AsyncSession, booking_id: uuid.UUID, user: User) -> dict:
    booking, slot, note = await _load(db, booking_id, user)
    return _note_dict(note, booking, slot)


async def save_notes(
    db: AsyncSession,
    booking_id: uuid.UUID,
    admin: User,
    summary: str | None,
    homework: str | None,
    vocabulary: str | None,
    notify_student: bool = True,
) -> dict:
    """Create or update the notes. The student is emailed the first time."""
    booking, slot, note = await _load(db, booking_id, admin)
    if booking.status not in ("confirmed", "completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "detail": "Notes can only be added to lessons that took place."},
        )
    is_new = note is None
    if is_new:
        note = LessonNote(booking_id=booking.id)
        db.add(note)
    note.summary, note.homework, note.vocabulary = _clean(summary), _clean(homework), _clean(vocabulary)
    await db.flush()
    await db.refresh(note)

    if is_new and notify_student and (note.summary or note.homework or note.vocabulary):
        try:
            from app.services.notification_service import send_email_later

            student = (await db.execute(select(User).where(User.id == booking.student_id))).scalar_one()
            words = len([line for line in (note.vocabulary or "").splitlines() if line.strip()])
            send_email_later(
                to=student.email,
                template_name="lesson_notes",
                context={
                    "first_name": student.first_name,
                    "lesson_date": timefmt.lesson_date(slot.start_at, student.timezone),
                    "homework": note.homework or "No homework this time.",
                    "word_count": str(words),
                    "notes_url": f"{settings.frontend_url}/notes",
                },
            )
        except Exception:
            logger.exception("Failed to send lesson notes email", extra={"booking_id": str(booking_id)})
    return _note_dict(note, booking, slot)


async def my_notes(db: AsyncSession, student: User) -> list[dict]:
    """All of a student's lesson notes, newest lesson first."""
    rows = (
        await db.execute(
            select(Booking, AvailabilitySlot, LessonNote)
            .join(AvailabilitySlot, Booking.slot_id == AvailabilitySlot.id)
            .join(LessonNote, LessonNote.booking_id == Booking.id)
            .where(Booking.student_id == student.id)
            .order_by(AvailabilitySlot.start_at.desc())
        )
    ).all()
    return [_note_dict(note, booking, slot) for booking, slot, note in rows]
