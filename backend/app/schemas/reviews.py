"""Review Pydantic schemas.

- ReviewCreate — request body for submitting a review
- ReviewResponse — response body for review data
- ReviewVisibilityUpdate — request body for hiding/unhiding a review (admin)
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.base import AppBaseModel


class ReviewCreate(AppBaseModel):
    """Request body for submitting a review."""

    booking_id: uuid.UUID
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)


class ReviewResponse(AppBaseModel):
    """Response body representing a review."""

    id: uuid.UUID
    booking_id: uuid.UUID
    student_id: uuid.UUID
    tutor_id: uuid.UUID
    rating: int
    comment: Optional[str] = None
    is_hidden: bool
    submitted_at: datetime


class ReviewVisibilityUpdate(AppBaseModel):
    """Request body for updating review visibility (admin only)."""

    is_hidden: bool
