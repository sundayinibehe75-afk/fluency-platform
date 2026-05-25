"""Messaging service — business logic for student–tutor messaging.

Functions:
- list_threads — returns all message threads for a user
- get_thread — returns paginated messages in a thread; marks as read
- send_message — validates recipient, stores message, logs email notification
- mark_read — marks a single message as read if user is the recipient
"""
import logging
import uuid
from typing import List

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.models.user import User
from app.schemas.messages import MessageResponse, ThreadResponse

logger = logging.getLogger(__name__)

MESSAGES_PER_PAGE = 50


async def list_threads(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> List[ThreadResponse]:
    """Return all message threads for the given user.

    Groups messages by the other participant, returning:
    - other_user_id, other_user_name
    - last_message_preview (first 100 chars of most recent message body)
    - last_message_at
    - unread_count (messages where recipient is user_id and is_read=False)
    """
    # Determine the "other user" for each message involving this user
    other_user_id_expr = case(
        (Message.sender_id == user_id, Message.recipient_id),
        else_=Message.sender_id,
    )

    # Subquery: get all messages involving this user, with the other_user_id
    messages_q = (
        select(
            other_user_id_expr.label("other_user_id"),
            Message.id,
            Message.body,
            Message.sent_at,
            Message.is_read,
            Message.recipient_id,
        )
        .where(
            or_(
                Message.sender_id == user_id,
                Message.recipient_id == user_id,
            )
        )
    ).subquery()

    # Group by other_user_id to get thread summaries
    thread_summary_q = (
        select(
            messages_q.c.other_user_id,
            func.max(messages_q.c.sent_at).label("last_message_at"),
            func.sum(
                case(
                    (
                        and_(
                            messages_q.c.recipient_id == user_id,
                            messages_q.c.is_read == False,  # noqa: E712
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("unread_count"),
        )
        .group_by(messages_q.c.other_user_id)
    )

    result = await db.execute(thread_summary_q)
    thread_rows = result.all()

    threads: List[ThreadResponse] = []
    for row in thread_rows:
        other_uid = row.other_user_id
        last_msg_at = row.last_message_at
        unread = int(row.unread_count)

        # Fetch the last message for preview
        last_msg_result = await db.execute(
            select(Message)
            .where(
                or_(
                    and_(Message.sender_id == user_id, Message.recipient_id == other_uid),
                    and_(Message.sender_id == other_uid, Message.recipient_id == user_id),
                )
            )
            .order_by(Message.sent_at.desc())
            .limit(1)
        )
        last_msg = last_msg_result.scalar_one_or_none()

        # Fetch the other user's name
        user_result = await db.execute(
            select(User).where(User.id == other_uid)
        )
        other_user = user_result.scalar_one_or_none()

        if last_msg is None or other_user is None:
            continue

        other_user_name = f"{other_user.first_name} {other_user.last_name}"
        preview = last_msg.body[:100]

        threads.append(
            ThreadResponse(
                other_user_id=other_uid,
                other_user_name=other_user_name,
                last_message_preview=preview,
                last_message_at=last_msg_at,
                unread_count=unread,
            )
        )

    # Sort by last_message_at descending
    threads.sort(key=lambda t: t.last_message_at, reverse=True)
    return threads


async def get_thread(
    db: AsyncSession,
    other_user_id: uuid.UUID,
    current_user_id: uuid.UUID,
    page: int = 1,
) -> List[MessageResponse]:
    """Return paginated messages between current_user and other_user.

    Messages are ordered by sent_at ASC (oldest first), paginated at 50/page.
    Also marks unread messages (where recipient is current_user) as read.
    """
    offset = (page - 1) * MESSAGES_PER_PAGE

    # Fetch messages between the two users
    query = (
        select(Message)
        .where(
            or_(
                and_(
                    Message.sender_id == current_user_id,
                    Message.recipient_id == other_user_id,
                ),
                and_(
                    Message.sender_id == other_user_id,
                    Message.recipient_id == current_user_id,
                ),
            )
        )
        .order_by(Message.sent_at.asc())
        .offset(offset)
        .limit(MESSAGES_PER_PAGE)
    )

    result = await db.execute(query)
    messages = result.scalars().all()

    # Mark unread messages as read where recipient is current_user
    for msg in messages:
        if msg.recipient_id == current_user_id and not msg.is_read:
            msg.is_read = True

    await db.flush()

    return [MessageResponse.model_validate(m) for m in messages]


async def send_message(
    db: AsyncSession,
    sender_id: uuid.UUID,
    recipient_id: uuid.UUID,
    body: str,
) -> MessageResponse:
    """Send a message from sender to recipient.

    Validations:
    - body must be <= 5000 characters
    - If sender is a student, recipient must have role="tutor"
    - If sender is a tutor, recipient must have role="student"
    Raises 403 if validation fails.

    After storing, logs that a delayed email notification should be scheduled.
    """
    # Validate body length
    if len(body) > 5000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "detail": "Message body must not exceed 5000 characters."},
        )

    # Fetch sender
    sender_result = await db.execute(select(User).where(User.id == sender_id))
    sender = sender_result.scalar_one_or_none()

    if sender is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Sender not found."},
        )

    # Fetch recipient
    recipient_result = await db.execute(select(User).where(User.id == recipient_id))
    recipient = recipient_result.scalar_one_or_none()

    if recipient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Recipient not found."},
        )

    # Role-based validation for v1 (single tutor):
    # Students can only message tutors; tutors can only message students
    if sender.role == "student" and recipient.role != "tutor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "FORBIDDEN", "detail": "Students can only message the tutor."},
        )

    if sender.role == "tutor" and recipient.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "FORBIDDEN", "detail": "Tutors can only message students."},
        )

    # Store the message
    message = Message(
        sender_id=sender_id,
        recipient_id=recipient_id,
        body=body,
    )
    db.add(message)
    await db.flush()

    # Log that a delayed email notification should be scheduled (5-min delay)
    logger.info(
        "Message sent — schedule delayed email notification (5 min)",
        extra={
            "message_id": str(message.id),
            "sender_id": str(sender_id),
            "recipient_id": str(recipient_id),
        },
    )

    return MessageResponse.model_validate(message)


async def mark_read(
    db: AsyncSession,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
) -> MessageResponse:
    """Mark a message as read. Only the recipient can mark it as read.

    Raises 404 if message not found.
    Raises 403 if user is not the recipient.
    """
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()

    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Message not found."},
        )

    if message.recipient_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "FORBIDDEN", "detail": "Only the recipient can mark a message as read."},
        )

    message.is_read = True
    await db.flush()

    return MessageResponse.model_validate(message)
