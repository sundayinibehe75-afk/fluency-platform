"""Availability router — manage tutor availability slots.

Endpoints:
- GET    /availability?tutor_id=...  — public, returns available future slots
- POST   /availability               — admin only, creates one or more slots
- PATCH  /availability/{id}          — admin only, updates a slot
- DELETE /availability/{id}          — admin only, deletes a slot (cancels booking if exists)
"""
import uuid
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.models.user import User
from app.schemas.availability import SlotCreate, SlotResponse, SlotUpdate
from app.services import availability_service

router = APIRouter(prefix="/availability", tags=["availability"])


@router.get("", response_model=List[SlotResponse])
async def list_available_slots(
    tutor_id: uuid.UUID = Query(..., description="Tutor ID to filter slots"),
    db: AsyncSession = Depends(get_db),
) -> List[SlotResponse]:
    """List available future slots for a tutor (public endpoint).

    Returns only slots with status 'available' and start_at in the future,
    ordered by start_at ascending.
    """
    return await availability_service.list_available_slots(db, tutor_id)


@router.post("", response_model=List[SlotResponse], status_code=201)
async def create_slots(
    body: SlotCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> List[SlotResponse]:
    """Create one or more availability slots (admin only).

    Supports optional recurrence configuration to generate weekly
    recurring slots up to 8 weeks ahead.

    - 201 Created on success
    - 403 Forbidden if user is not admin
    - 409 Conflict if any slot overlaps an existing slot
    """
    return await availability_service.create_slots(db, body)


@router.patch("/{slot_id}", response_model=SlotResponse)
async def update_slot(
    slot_id: uuid.UUID,
    body: SlotUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> SlotResponse:
    """Update an availability slot (admin only).

    Only provided fields are updated (partial update).

    - 200 OK on success
    - 403 Forbidden if user is not admin
    - 404 Not Found if slot does not exist
    - 409 Conflict if updated times overlap another slot
    """
    return await availability_service.update_slot(db, slot_id, body)


@router.delete("/{slot_id}", status_code=204)
async def delete_slot(
    slot_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> None:
    """Delete an availability slot (admin only).

    If the slot has a confirmed booking, the booking is cancelled and
    a notification is logged for the affected student.

    - 204 No Content on success
    - 403 Forbidden if user is not admin
    - 404 Not Found if slot does not exist
    """
    await availability_service.delete_slot(db, slot_id)
