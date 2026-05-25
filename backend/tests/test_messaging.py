"""Unit tests for messaging schemas, service logic, and router.

Tests cover:
- Schema validation (MessageCreate, MessageResponse, ThreadResponse)
- Service logic (send_message role validation, mark_read ownership)
- Using mocked DB sessions for service-level tests
"""
import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.schemas.messages import MessageCreate, MessageResponse, ThreadResponse


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestMessageCreate:
    """Tests for MessageCreate schema validation."""

    def test_valid_message_create(self):
        msg = MessageCreate(
            recipient_id=uuid.uuid4(),
            body="Hello, tutor!",
        )
        assert len(msg.body) == 13

    def test_body_max_length_accepted(self):
        body = "a" * 5000
        msg = MessageCreate(
            recipient_id=uuid.uuid4(),
            body=body,
        )
        assert len(msg.body) == 5000

    def test_body_exceeds_max_length_rejected(self):
        body = "a" * 5001
        with pytest.raises(ValidationError):
            MessageCreate(
                recipient_id=uuid.uuid4(),
                body=body,
            )

    def test_empty_body_allowed_at_schema_level(self):
        """Empty body is allowed at schema level; service may reject it."""
        msg = MessageCreate(
            recipient_id=uuid.uuid4(),
            body="",
        )
        assert msg.body == ""

    def test_missing_recipient_id_rejected(self):
        with pytest.raises(ValidationError):
            MessageCreate(body="Hello")  # type: ignore[call-arg]

    def test_missing_body_rejected(self):
        with pytest.raises(ValidationError):
            MessageCreate(recipient_id=uuid.uuid4())  # type: ignore[call-arg]


class TestMessageResponse:
    """Tests for MessageResponse schema."""

    def test_valid_message_response(self):
        now = datetime.now(tz=timezone.utc)
        resp = MessageResponse(
            id=uuid.uuid4(),
            sender_id=uuid.uuid4(),
            recipient_id=uuid.uuid4(),
            body="Test message",
            is_read=False,
            sent_at=now,
        )
        assert resp.is_read is False
        assert resp.body == "Test message"

    def test_from_attributes_mode(self):
        """Verify from_attributes (ORM mode) works."""
        now = datetime.now(tz=timezone.utc)
        msg_id = uuid.uuid4()

        class FakeMessage:
            id = msg_id
            sender_id = uuid.uuid4()
            recipient_id = uuid.uuid4()
            body = "ORM test"
            is_read = True
            sent_at = now

        resp = MessageResponse.model_validate(FakeMessage())
        assert resp.id == msg_id
        assert resp.is_read is True


class TestThreadResponse:
    """Tests for ThreadResponse schema."""

    def test_valid_thread_response(self):
        now = datetime.now(tz=timezone.utc)
        thread = ThreadResponse(
            other_user_id=uuid.uuid4(),
            other_user_name="Jane Doe",
            last_message_preview="Hello, how are you?",
            last_message_at=now,
            unread_count=3,
        )
        assert thread.unread_count == 3
        assert thread.other_user_name == "Jane Doe"

    def test_preview_max_100_chars(self):
        now = datetime.now(tz=timezone.utc)
        preview = "x" * 100
        thread = ThreadResponse(
            other_user_id=uuid.uuid4(),
            other_user_name="John Smith",
            last_message_preview=preview,
            last_message_at=now,
            unread_count=0,
        )
        assert len(thread.last_message_preview) == 100

    def test_preview_exceeds_100_chars_rejected(self):
        now = datetime.now(tz=timezone.utc)
        preview = "x" * 101
        with pytest.raises(ValidationError):
            ThreadResponse(
                other_user_id=uuid.uuid4(),
                other_user_name="John Smith",
                last_message_preview=preview,
                last_message_at=now,
                unread_count=0,
            )


# ---------------------------------------------------------------------------
# Service logic tests (using mocked DB)
# ---------------------------------------------------------------------------


class TestSendMessageValidation:
    """Tests for send_message role-based validation logic."""

    def test_student_cannot_message_another_student(self):
        """A student sending to another student should get 403."""
        from fastapi import HTTPException

        from app.services.messaging_service import send_message

        sender_id = uuid.uuid4()
        recipient_id = uuid.uuid4()

        mock_sender = MagicMock()
        mock_sender.id = sender_id
        mock_sender.role = "student"

        mock_recipient = MagicMock()
        mock_recipient.id = recipient_id
        mock_recipient.role = "student"

        db = AsyncMock()
        sender_result = MagicMock()
        sender_result.scalar_one_or_none.return_value = mock_sender
        recipient_result = MagicMock()
        recipient_result.scalar_one_or_none.return_value = mock_recipient
        db.execute = AsyncMock(side_effect=[sender_result, recipient_result])

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(send_message(db, sender_id, recipient_id, "Hello"))

        assert exc_info.value.status_code == 403

    def test_tutor_cannot_message_another_tutor(self):
        """A tutor sending to another tutor should get 403."""
        from fastapi import HTTPException

        from app.services.messaging_service import send_message

        sender_id = uuid.uuid4()
        recipient_id = uuid.uuid4()

        mock_sender = MagicMock()
        mock_sender.id = sender_id
        mock_sender.role = "tutor"

        mock_recipient = MagicMock()
        mock_recipient.id = recipient_id
        mock_recipient.role = "tutor"

        db = AsyncMock()
        sender_result = MagicMock()
        sender_result.scalar_one_or_none.return_value = mock_sender
        recipient_result = MagicMock()
        recipient_result.scalar_one_or_none.return_value = mock_recipient
        db.execute = AsyncMock(side_effect=[sender_result, recipient_result])

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(send_message(db, sender_id, recipient_id, "Hello"))

        assert exc_info.value.status_code == 403

    def test_student_can_message_tutor(self):
        """A student sending to a tutor should succeed."""
        from app.services.messaging_service import send_message

        sender_id = uuid.uuid4()
        recipient_id = uuid.uuid4()

        mock_sender = MagicMock()
        mock_sender.id = sender_id
        mock_sender.role = "student"

        mock_recipient = MagicMock()
        mock_recipient.id = recipient_id
        mock_recipient.role = "tutor"

        mock_message = MagicMock()
        mock_message.id = uuid.uuid4()
        mock_message.sender_id = sender_id
        mock_message.recipient_id = recipient_id
        mock_message.body = "Hello tutor"
        mock_message.is_read = False
        mock_message.sent_at = datetime.now(tz=timezone.utc)

        db = AsyncMock()
        sender_result = MagicMock()
        sender_result.scalar_one_or_none.return_value = mock_sender
        recipient_result = MagicMock()
        recipient_result.scalar_one_or_none.return_value = mock_recipient
        db.execute = AsyncMock(side_effect=[sender_result, recipient_result])
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.services.messaging_service.Message") as MockMessage:
            MockMessage.return_value = mock_message
            result = asyncio.run(send_message(db, sender_id, recipient_id, "Hello tutor"))

        assert result.sender_id == sender_id
        assert result.recipient_id == recipient_id

    def test_tutor_can_message_student(self):
        """A tutor sending to a student should succeed."""
        from app.services.messaging_service import send_message

        sender_id = uuid.uuid4()
        recipient_id = uuid.uuid4()

        mock_sender = MagicMock()
        mock_sender.id = sender_id
        mock_sender.role = "tutor"

        mock_recipient = MagicMock()
        mock_recipient.id = recipient_id
        mock_recipient.role = "student"

        mock_message = MagicMock()
        mock_message.id = uuid.uuid4()
        mock_message.sender_id = sender_id
        mock_message.recipient_id = recipient_id
        mock_message.body = "Hello student"
        mock_message.is_read = False
        mock_message.sent_at = datetime.now(tz=timezone.utc)

        db = AsyncMock()
        sender_result = MagicMock()
        sender_result.scalar_one_or_none.return_value = mock_sender
        recipient_result = MagicMock()
        recipient_result.scalar_one_or_none.return_value = mock_recipient
        db.execute = AsyncMock(side_effect=[sender_result, recipient_result])
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.services.messaging_service.Message") as MockMessage:
            MockMessage.return_value = mock_message
            result = asyncio.run(send_message(db, sender_id, recipient_id, "Hello student"))

        assert result.sender_id == sender_id
        assert result.recipient_id == recipient_id

    def test_body_over_5000_chars_rejected(self):
        """Body exceeding 5000 chars should raise 400."""
        from fastapi import HTTPException

        from app.services.messaging_service import send_message

        db = AsyncMock()
        body = "x" * 5001

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(send_message(db, uuid.uuid4(), uuid.uuid4(), body))

        assert exc_info.value.status_code == 400

    def test_recipient_not_found_raises_404(self):
        """Non-existent recipient should raise 404."""
        from fastapi import HTTPException

        from app.services.messaging_service import send_message

        sender_id = uuid.uuid4()
        recipient_id = uuid.uuid4()

        mock_sender = MagicMock()
        mock_sender.id = sender_id
        mock_sender.role = "student"

        db = AsyncMock()
        sender_result = MagicMock()
        sender_result.scalar_one_or_none.return_value = mock_sender
        recipient_result = MagicMock()
        recipient_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(side_effect=[sender_result, recipient_result])

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(send_message(db, sender_id, recipient_id, "Hello"))

        assert exc_info.value.status_code == 404


class TestMarkReadValidation:
    """Tests for mark_read ownership enforcement."""

    def test_recipient_can_mark_read(self):
        """The recipient should be able to mark a message as read."""
        from app.services.messaging_service import mark_read

        message_id = uuid.uuid4()
        recipient_id = uuid.uuid4()

        mock_message = MagicMock()
        mock_message.id = message_id
        mock_message.sender_id = uuid.uuid4()
        mock_message.recipient_id = recipient_id
        mock_message.body = "Test"
        mock_message.is_read = False
        mock_message.sent_at = datetime.now(tz=timezone.utc)

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_message
        db.execute = AsyncMock(return_value=result_mock)
        db.flush = AsyncMock()

        asyncio.run(mark_read(db, message_id, recipient_id))
        assert mock_message.is_read is True

    def test_non_recipient_cannot_mark_read(self):
        """A user who is not the recipient should get 403."""
        from fastapi import HTTPException

        from app.services.messaging_service import mark_read

        message_id = uuid.uuid4()
        other_user_id = uuid.uuid4()

        mock_message = MagicMock()
        mock_message.id = message_id
        mock_message.sender_id = uuid.uuid4()
        mock_message.recipient_id = uuid.uuid4()  # Different from other_user_id
        mock_message.body = "Test"
        mock_message.is_read = False
        mock_message.sent_at = datetime.now(tz=timezone.utc)

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_message
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(mark_read(db, message_id, other_user_id))

        assert exc_info.value.status_code == 403

    def test_message_not_found_raises_404(self):
        """Non-existent message should raise 404."""
        from fastapi import HTTPException

        from app.services.messaging_service import mark_read

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(mark_read(db, uuid.uuid4(), uuid.uuid4()))

        assert exc_info.value.status_code == 404
