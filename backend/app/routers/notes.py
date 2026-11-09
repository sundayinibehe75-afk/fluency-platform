"""Lesson notes router.

Endpoints:
- GET /bookings/{id}/notes — student (own lesson) or admin
- PUT /bookings/{id}/notes — admin, create or update notes
- GET /notes/me            — student, all their lesson notes
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.models.user import User
from app.services import notes_service

router = APIRouter(tags=["notes"])


class NotesBody(BaseModel):
    summary: Optional[str] = Field(None, max_length=5000)
    homework: Optional[str] = Field(None, max_length=5000)
    vocabulary: Optional[str] = Field(None, max_length=10000)


@router.get("/bookings/{booking_id}/notes")
async def get_notes(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student", "admin")),
) -> dict:
    return await notes_service.get_notes(db, booking_id, current_user)


@router.put("/bookings/{booking_id}/notes")
async def save_notes(
    booking_id: uuid.UUID,
    body: NotesBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> dict:
    return await notes_service.save_notes(
        db, booking_id, current_user, body.summary, body.homework, body.vocabulary
    )


@router.get("/notes/me")
async def my_notes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student")),
) -> list[dict]:
    return await notes_service.my_notes(db, current_user)
