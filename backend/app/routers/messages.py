"""Messages router — endpoints for student–tutor messaging.

Endpoints:
- GET /messages/threads — student/tutor auth, list all threads
- GET /messages/threads/{user_id} — student/tutor auth, get paginated thread
- POST /messages — student/tutor auth, send a message
- PATCH /messages/{id}/read — student/tutor auth, mark message as read
"""
import uuid
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.models.user import User
from app.schemas.messages import MessageCreate, MessageResponse, ThreadResponse
from app.services import messaging_service

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/threads", response_model=List[ThreadResponse])
async def list_threads(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student", "tutor")),
) -> List[ThreadResponse]:
    """List all message threads for the current user."""
    return await messaging_service.list_threads(db=db, user_id=current_user.id)


@router.get("/threads/{user_id}", response_model=List[MessageResponse])
async def get_thread(
    user_id: uuid.UUID,
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student", "tutor")),
) -> List[MessageResponse]:
    """Get paginated messages in a thread with another user."""
    return await messaging_service.get_thread(
        db=db,
        other_user_id=user_id,
        current_user_id=current_user.id,
        page=page,
    )


@router.post("", response_model=MessageResponse, status_code=201)
async def send_message(
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student", "tutor")),
) -> MessageResponse:
    """Send a message to another user."""
    return await messaging_service.send_message(
        db=db,
        sender_id=current_user.id,
        recipient_id=body.recipient_id,
        body=body.body,
    )


@router.patch("/{message_id}/read", response_model=MessageResponse)
async def mark_read(
    message_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student", "tutor")),
) -> MessageResponse:
    """Mark a message as read (only the recipient can do this)."""
    return await messaging_service.mark_read(
        db=db,
        message_id=message_id,
        user_id=current_user.id,
    )
