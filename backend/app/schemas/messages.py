"""Pydantic schemas for the messaging domain.

- MessageCreate — request body for sending a message
- MessageResponse — single message in a thread
- ThreadResponse — summary of a message thread
"""
import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import AppBaseModel


class MessageCreate(AppBaseModel):
    """Request body for POST /messages."""

    recipient_id: uuid.UUID
    body: str = Field(..., max_length=5000)


class MessageResponse(AppBaseModel):
    """Single message representation returned in thread views."""

    id: uuid.UUID
    sender_id: uuid.UUID
    recipient_id: uuid.UUID
    body: str
    is_read: bool
    sent_at: datetime


class ThreadResponse(AppBaseModel):
    """Summary of a message thread with another user."""

    other_user_id: uuid.UUID
    other_user_name: str
    last_message_preview: str = Field(..., max_length=100)
    last_message_at: datetime
    unread_count: int
