"""Tests for the video service — Daily.co room creation."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    """Mock settings to avoid requiring real env vars for tests."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_123")
    monkeypatch.setenv("RESEND_API_KEY", "re_test_123")
    monkeypatch.setenv("DAILY_API_KEY", "daily_test_123")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")


class TestCreateRoom:
    """Tests for video_service.create_room."""

    @pytest.mark.asyncio
    async def test_create_room_success(self):
        """create_room should POST to Daily.co and store the room URL."""
        from app.services import video_service

        booking_id = uuid.uuid4()
        slot_id = uuid.uuid4()
        lesson_end = datetime(2025, 7, 20, 15, 0, 0, tzinfo=timezone.utc)
        expected_exp = int(lesson_end.timestamp()) + 1800
        room_url = "https://fluency.daily.co/abc123"

        # Mock booking
        mock_booking = MagicMock()
        mock_booking.id = booking_id
        mock_booking.slot_id = slot_id
        mock_booking.video_room_url = None

        # Mock slot
        mock_slot = MagicMock()
        mock_slot.id = slot_id
        mock_slot.end_at = lesson_end

        # Mock DB session
        mock_db = AsyncMock()
        call_count = [0]

        async def mock_execute(query):
            result = MagicMock()
            if call_count[0] == 0:
                result.scalar_one_or_none.return_value = mock_booking
            else:
                result.scalar_one_or_none.return_value = mock_slot
            call_count[0] += 1
            return result

        mock_db.execute = mock_execute
        mock_db.flush = AsyncMock()

        # Mock httpx response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"url": room_url, "name": "abc123"}
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.video_service.httpx.AsyncClient") as mock_client_cls, \
             patch("app.services.video_service.settings") as mock_settings_obj:
            mock_settings_obj.daily_api_key = "daily_test_key"
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await video_service.create_room(mock_db, booking_id)

        assert result == room_url
        assert mock_booking.video_room_url == room_url
        mock_db.flush.assert_called_once()

        # Verify the POST was made with correct params
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://api.daily.co/v1/rooms"
        assert call_args[1]["headers"]["Authorization"] == "Bearer daily_test_key"
        assert call_args[1]["json"] == {"properties": {"exp": expected_exp}}

    @pytest.mark.asyncio
    async def test_create_room_booking_not_found(self):
        """create_room should return None if booking doesn't exist."""
        from app.services import video_service

        booking_id = uuid.uuid4()

        mock_db = AsyncMock()

        async def mock_execute(query):
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        mock_db.execute = mock_execute

        result = await video_service.create_room(mock_db, booking_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_create_room_slot_not_found(self):
        """create_room should return None if slot doesn't exist."""
        from app.services import video_service

        booking_id = uuid.uuid4()
        slot_id = uuid.uuid4()

        mock_booking = MagicMock()
        mock_booking.id = booking_id
        mock_booking.slot_id = slot_id

        mock_db = AsyncMock()
        call_count = [0]

        async def mock_execute(query):
            result = MagicMock()
            if call_count[0] == 0:
                result.scalar_one_or_none.return_value = mock_booking
            else:
                result.scalar_one_or_none.return_value = None
            call_count[0] += 1
            return result

        mock_db.execute = mock_execute

        result = await video_service.create_room(mock_db, booking_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_create_room_daily_api_error(self):
        """create_room should return None and log on Daily.co API error."""
        from app.services import video_service

        booking_id = uuid.uuid4()
        slot_id = uuid.uuid4()
        lesson_end = datetime(2025, 7, 20, 15, 0, 0, tzinfo=timezone.utc)

        mock_booking = MagicMock()
        mock_booking.id = booking_id
        mock_booking.slot_id = slot_id

        mock_slot = MagicMock()
        mock_slot.id = slot_id
        mock_slot.end_at = lesson_end

        mock_db = AsyncMock()
        call_count = [0]

        async def mock_execute(query):
            result = MagicMock()
            if call_count[0] == 0:
                result.scalar_one_or_none.return_value = mock_booking
            else:
                result.scalar_one_or_none.return_value = mock_slot
            call_count[0] += 1
            return result

        mock_db.execute = mock_execute

        # Mock httpx to raise an HTTP error
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("app.services.video_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "401 Unauthorized",
                request=MagicMock(),
                response=mock_response,
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await video_service.create_room(mock_db, booking_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_create_room_network_error(self):
        """create_room should return None on network/connection errors."""
        from app.services import video_service

        booking_id = uuid.uuid4()
        slot_id = uuid.uuid4()
        lesson_end = datetime(2025, 7, 20, 15, 0, 0, tzinfo=timezone.utc)

        mock_booking = MagicMock()
        mock_booking.id = booking_id
        mock_booking.slot_id = slot_id

        mock_slot = MagicMock()
        mock_slot.id = slot_id
        mock_slot.end_at = lesson_end

        mock_db = AsyncMock()
        call_count = [0]

        async def mock_execute(query):
            result = MagicMock()
            if call_count[0] == 0:
                result.scalar_one_or_none.return_value = mock_booking
            else:
                result.scalar_one_or_none.return_value = mock_slot
            call_count[0] += 1
            return result

        mock_db.execute = mock_execute

        with patch("app.services.video_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await video_service.create_room(mock_db, booking_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_create_room_expiry_calculation(self):
        """Room expiry should be lesson end time + 30 minutes (1800 seconds)."""
        from app.services import video_service

        booking_id = uuid.uuid4()
        slot_id = uuid.uuid4()
        # Use a specific time to verify calculation
        lesson_end = datetime(2025, 8, 1, 10, 30, 0, tzinfo=timezone.utc)
        expected_exp = int(lesson_end.timestamp()) + 1800

        mock_booking = MagicMock()
        mock_booking.id = booking_id
        mock_booking.slot_id = slot_id
        mock_booking.video_room_url = None

        mock_slot = MagicMock()
        mock_slot.id = slot_id
        mock_slot.end_at = lesson_end

        mock_db = AsyncMock()
        call_count = [0]

        async def mock_execute(query):
            result = MagicMock()
            if call_count[0] == 0:
                result.scalar_one_or_none.return_value = mock_booking
            else:
                result.scalar_one_or_none.return_value = mock_slot
            call_count[0] += 1
            return result

        mock_db.execute = mock_execute
        mock_db.flush = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"url": "https://fluency.daily.co/room1"}
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.video_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await video_service.create_room(mock_db, booking_id)

        # Verify the exp value sent to Daily.co
        call_args = mock_client.post.call_args
        sent_exp = call_args[1]["json"]["properties"]["exp"]
        assert sent_exp == expected_exp
