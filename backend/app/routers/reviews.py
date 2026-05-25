"""Reviews router — endpoints for submitting and managing reviews.

Endpoints:
- POST /reviews — student auth, submit a review for a completed booking
- GET /reviews?tutor_id=... — public, list visible reviews for a tutor
- PATCH /reviews/{id}/visibility — admin auth, hide/unhide a review
"""
import uuid
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.reviews import ReviewCreate, ReviewResponse, ReviewVisibilityUpdate
from app.services import review_service

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("", response_model=ReviewResponse, status_code=201)
async def submit_review(
    body: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student")),
) -> ReviewResponse:
    """Submit a review for a completed booking."""
    return await review_service.submit_review(
        db=db,
        booking_id=body.booking_id,
        student_id=current_user.id,
        rating=body.rating,
        comment=body.comment,
    )


@router.get("", response_model=List[ReviewResponse])
async def list_reviews(
    tutor_id: uuid.UUID = Query(..., description="Tutor ID to list reviews for"),
    db: AsyncSession = Depends(get_db),
) -> List[ReviewResponse]:
    """List visible reviews for a tutor (public endpoint)."""
    return await review_service.list_reviews(db=db, tutor_id=tutor_id)


@router.patch("/{review_id}/visibility", response_model=ReviewResponse)
async def set_visibility(
    review_id: uuid.UUID,
    body: ReviewVisibilityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> ReviewResponse:
    """Hide or unhide a review (admin only)."""
    return await review_service.set_visibility(
        db=db,
        review_id=review_id,
        is_hidden=body.is_hidden,
    )
