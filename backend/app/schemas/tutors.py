"""Tutor profile schemas — request/response models for the tutors router."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.base import AppBaseModel


class ReviewSummary(AppBaseModel):
    """Nested schema for a single review in the tutor profile response."""

    first_name: str
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None
    submitted_at: datetime


class TutorProfileResponse(AppBaseModel):
    """Full tutor profile including aggregate rating and recent reviews."""

    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    bio: Optional[str] = None
    photo_url: Optional[str] = None
    spoken_languages: list[str] = []
    specialisms: list[str] = []
    cefr_levels_taught: list[str] = []
    years_experience: Optional[int] = None
    avg_rating: float
    review_count: int
    recent_reviews: list[ReviewSummary] = []
    updated_at: datetime


class TutorUpdateRequest(AppBaseModel):
    """Partial update schema — all fields optional."""

    display_name: Optional[str] = Field(None, max_length=150)
    bio: Optional[str] = None
    photo_url: Optional[str] = Field(None, max_length=500)
    spoken_languages: Optional[list[str]] = None
    specialisms: Optional[list[str]] = None
    cefr_levels_taught: Optional[list[str]] = None
    years_experience: Optional[int] = None
