"""Tutor profile service — business logic for fetching and updating tutor profiles."""
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review
from app.models.tutor import Tutor
from app.models.user import User
from app.schemas.tutors import ReviewSummary, TutorProfileResponse, TutorUpdateRequest


async def get_tutor_profile(
    db: AsyncSession, tutor_id: uuid.UUID
) -> TutorProfileResponse:
    """Fetch a tutor by ID and join the 5 most recent visible reviews.

    Raises HTTP 404 if the tutor does not exist.
    """
    # Fetch tutor
    result = await db.execute(select(Tutor).where(Tutor.id == tutor_id))
    tutor: Tutor | None = result.scalar_one_or_none()

    if tutor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Tutor not found."},
        )

    # Fetch 5 most recent visible reviews with reviewer first_name
    reviews_query = (
        select(Review, User.first_name)
        .join(User, Review.student_id == User.id)
        .where(Review.tutor_id == tutor_id, Review.is_hidden == False)  # noqa: E712
        .order_by(Review.submitted_at.desc())
        .limit(5)
    )
    reviews_result = await db.execute(reviews_query)
    review_rows = reviews_result.all()

    recent_reviews = [
        ReviewSummary(
            first_name=first_name,
            rating=review.rating,
            comment=review.comment,
            submitted_at=review.submitted_at,
        )
        for review, first_name in review_rows
    ]

    return TutorProfileResponse(
        id=tutor.id,
        user_id=tutor.user_id,
        display_name=tutor.display_name,
        bio=tutor.bio,
        photo_url=tutor.photo_url,
        spoken_languages=tutor.spoken_languages,
        specialisms=tutor.specialisms,
        cefr_levels_taught=tutor.cefr_levels_taught,
        years_experience=tutor.years_experience,
        avg_rating=float(tutor.avg_rating),
        review_count=tutor.review_count,
        recent_reviews=recent_reviews,
        updated_at=tutor.updated_at,
    )


async def update_tutor_profile(
    db: AsyncSession, tutor_id: uuid.UUID, data: TutorUpdateRequest
) -> TutorProfileResponse:
    """Update only the provided fields on a tutor profile (admin only).

    Raises HTTP 404 if the tutor does not exist.
    Returns the updated profile (including recent reviews).
    """
    # Fetch tutor
    result = await db.execute(select(Tutor).where(Tutor.id == tutor_id))
    tutor: Tutor | None = result.scalar_one_or_none()

    if tutor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Tutor not found."},
        )

    # Apply only provided (non-None) fields
    update_data: dict[str, Any] = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tutor, field, value)

    await db.flush()

    # Return the updated profile with reviews
    return await get_tutor_profile(db, tutor_id)
