"""Tutors router — public profile retrieval and admin profile updates.

Endpoints:
- GET  /tutors/{id}  — public, no auth required
- PATCH /tutors/{id} — requires admin role
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.models.user import User
from app.schemas.tutors import TutorProfileResponse, TutorUpdateRequest
from app.services import tutor_service

router = APIRouter(prefix="/tutors", tags=["tutors"])


@router.get("/{tutor_id}", response_model=TutorProfileResponse)
async def get_tutor_profile(
    tutor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TutorProfileResponse:
    """Retrieve a tutor's public profile including recent reviews.

    - 200 OK on success
    - 404 Not Found if tutor does not exist
    """
    return await tutor_service.get_tutor_profile(db, tutor_id)


@router.patch("/{tutor_id}", response_model=TutorProfileResponse)
async def update_tutor_profile(
    tutor_id: uuid.UUID,
    body: TutorUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> TutorProfileResponse:
    """Update tutor profile fields (admin only).

    Only provided fields are updated (partial update).

    - 200 OK on success
    - 403 Forbidden if user is not admin
    - 404 Not Found if tutor does not exist
    """
    return await tutor_service.update_tutor_profile(db, tutor_id, body)
