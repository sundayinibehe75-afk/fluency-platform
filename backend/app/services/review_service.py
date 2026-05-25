"""Review service — business logic for reviews and ratings.

Functions:
- submit_review — validates booking, rejects duplicates, stores review, recalculates avg_rating
- list_reviews — returns visible reviews for a tutor sorted by submitted_at DESC
- set_visibility — admin toggle for hiding/unhiding reviews; recalculates avg_rating
"""
import logging
import uuid
from typing import List

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.review import Review
from app.models.tutor import Tutor
from app.schemas.reviews import ReviewResponse

logger = logging.getLogger(__name__)


async def _recalculate_tutor_rating(db: AsyncSession, tutor_id: uuid.UUID) -> None:
    """Recalculate avg_rating and review_count for a tutor based on visible reviews."""
    result = await db.execute(
        select(
            func.count(Review.id).label("cnt"),
            func.avg(Review.rating).label("avg"),
        ).where(
            Review.tutor_id == tutor_id,
            Review.is_hidden == False,  # noqa: E712
        )
    )
    row = result.one()
    count = row.cnt or 0
    avg = float(row.avg) if row.avg is not None else 0.0
    avg_rounded = round(avg, 1)

    tutor_result = await db.execute(select(Tutor).where(Tutor.id == tutor_id))
    tutor = tutor_result.scalar_one_or_none()
    if tutor:
        tutor.avg_rating = avg_rounded
        tutor.review_count = count


async def submit_review(
    db: AsyncSession,
    booking_id: uuid.UUID,
    student_id: uuid.UUID,
    rating: int,
    comment: str | None = None,
) -> ReviewResponse:
    """Submit a review for a completed booking.

    Validations:
    - Booking must exist and have status 'completed'
    - Booking must belong to the student (403 FORBIDDEN)
    - No duplicate review for the same booking (409 REVIEW_EXISTS)

    After storing, recalculates avg_rating and review_count on the tutor.
    """
    # Fetch booking
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()

    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Booking not found."},
        )

    # Verify booking belongs to student
    if booking.student_id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "FORBIDDEN", "detail": "This booking does not belong to you."},
        )

    # Verify booking is completed
    if booking.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "FORBIDDEN", "detail": "Reviews can only be submitted for completed bookings."},
        )

    # Check for duplicate review
    existing_result = await db.execute(
        select(Review).where(Review.booking_id == booking_id)
    )
    existing = existing_result.scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "REVIEW_EXISTS", "detail": "A review has already been submitted for this booking."},
        )

    # Create review
    review = Review(
        booking_id=booking_id,
        student_id=student_id,
        tutor_id=booking.tutor_id,
        rating=rating,
        comment=comment,
    )
    db.add(review)
    await db.flush()

    # Recalculate tutor avg_rating and review_count
    await _recalculate_tutor_rating(db, booking.tutor_id)

    logger.info(
        "Review submitted",
        extra={
            "review_id": str(review.id),
            "booking_id": str(booking_id),
            "tutor_id": str(booking.tutor_id),
            "rating": rating,
        },
    )

    return ReviewResponse.model_validate(review)


async def list_reviews(
    db: AsyncSession,
    tutor_id: uuid.UUID,
) -> List[ReviewResponse]:
    """Return visible reviews for a tutor, sorted by submitted_at DESC."""
    result = await db.execute(
        select(Review)
        .where(
            Review.tutor_id == tutor_id,
            Review.is_hidden == False,  # noqa: E712
        )
        .order_by(Review.submitted_at.desc())
    )
    reviews = result.scalars().all()
    return [ReviewResponse.model_validate(r) for r in reviews]


async def set_visibility(
    db: AsyncSession,
    review_id: uuid.UUID,
    is_hidden: bool,
) -> ReviewResponse:
    """Set the visibility of a review (admin only).

    Raises 404 if review not found.
    After updating, recalculates avg_rating excluding hidden reviews.
    """
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()

    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Review not found."},
        )

    review.is_hidden = is_hidden
    await db.flush()

    # Recalculate tutor avg_rating excluding hidden reviews
    await _recalculate_tutor_rating(db, review.tutor_id)

    logger.info(
        "Review visibility updated",
        extra={
            "review_id": str(review_id),
            "is_hidden": is_hidden,
        },
    )

    return ReviewResponse.model_validate(review)
