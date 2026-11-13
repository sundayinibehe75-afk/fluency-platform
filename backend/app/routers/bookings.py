"""Bookings router — endpoints for managing lesson bookings.

Endpoints:
- POST /bookings — student auth, create a booking
- POST /bookings/weekly — student auth, same time every week with plan lessons
- GET /bookings — student/admin auth, list bookings
- GET /bookings/{id} — student/admin auth, get a single booking
- POST /bookings/{id}/cancel — student/admin auth, cancel a booking
- POST /bookings/{id}/reschedule — student/admin auth, move to another slot
"""
import uuid
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.bookings import (
    BookingCreate,
    BookingReschedule,
    BookingResponse,
    BookingWeekly,
    WeeklyBookingResponse,
)
from app.services import booking_service

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingResponse, status_code=201)
async def create_booking(
    body: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student")),
) -> BookingResponse:
    """Initiate a booking for the authenticated student."""
    return await booking_service.create_booking(
        db=db,
        student_id=current_user.id,
        slot_id=body.slot_id,
        booking_type=body.booking_type,
        start_at=body.start_at,
        minutes=body.minutes,
    )


@router.post("/weekly", response_model=WeeklyBookingResponse, status_code=201)
async def book_weekly(
    body: BookingWeekly,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student")),
) -> WeeklyBookingResponse:
    """Book this time every week while the student's plan lessons last."""
    result = await booking_service.book_weekly(
        db=db, student=current_user, slot_id=body.slot_id, start_at=body.start_at, minutes=body.minutes
    )
    return WeeklyBookingResponse(**result)


@router.get("", response_model=List[BookingResponse])
async def list_bookings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student", "admin")),
) -> List[BookingResponse]:
    """List bookings for the current user (student sees own, admin sees all)."""
    return await booking_service.list_bookings(db=db, user=current_user)


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student", "admin")),
) -> BookingResponse:
    """Get a single booking by ID with ownership enforcement."""
    return await booking_service.get_booking(
        db=db,
        booking_id=booking_id,
        user=current_user,
    )


@router.post("/{booking_id}/cancel", response_model=dict)
async def cancel_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student", "admin")),
) -> dict:
    """Cancel a booking (own booking for students, any booking for admins).

    Returns whether a refund was issued.
    """
    result = await booking_service.cancel_booking(
        db=db,
        booking_id=booking_id,
        actor=current_user,
    )
    return {"status": "cancelled", **result}


@router.post("/{booking_id}/reschedule", response_model=BookingResponse)
async def reschedule_booking(
    booking_id: uuid.UUID,
    body: BookingReschedule,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student", "admin")),
) -> BookingResponse:
    """Move a confirmed lesson to another free slot.

    Students can reschedule up to 12 hours before the lesson; the admin any time.
    """
    return await booking_service.reschedule_booking(
        db=db,
        booking_id=booking_id,
        new_slot_id=body.new_slot_id,
        actor=current_user,
        start_at=body.start_at,
    )
