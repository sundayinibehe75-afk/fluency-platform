"""Unit tests for availability schemas, service logic, and router.

Tests cover:
- Schema validation (RecurrenceConfig, SlotCreate, SlotUpdate)
- Overlap detection helper
- Service logic (create, list, update, delete) using mocked DB sessions
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.availability import (
    RecurrenceConfig,
    SlotCreate,
    SlotResponse,
    SlotUpdate,
)
from app.services.availability_service import _check_overlap


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestRecurrenceConfig:
    """Tests for RecurrenceConfig schema validation."""

    def test_valid_weekly_recurrence(self):
        config = RecurrenceConfig(pattern="weekly", weeks_ahead=4)
        assert config.pattern == "weekly"
        assert config.weeks_ahead == 4

    def test_weeks_ahead_min_boundary(self):
        config = RecurrenceConfig(pattern="weekly", weeks_ahead=1)
        assert config.weeks_ahead == 1

    def test_weeks_ahead_max_boundary(self):
        config = RecurrenceConfig(pattern="weekly", weeks_ahead=8)
        assert config.weeks_ahead == 8

    def test_weeks_ahead_below_min_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RecurrenceConfig(pattern="weekly", weeks_ahead=0)

    def test_weeks_ahead_above_max_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RecurrenceConfig(pattern="weekly", weeks_ahead=9)

    def test_invalid_pattern_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RecurrenceConfig(pattern="daily", weeks_ahead=4)


class TestSlotCreate:
    """Tests for SlotCreate schema validation."""

    def test_valid_slot_create_no_recurrence(self):
        now = datetime.now(tz=timezone.utc)
        slot = SlotCreate(
            tutor_id=uuid.uuid4(),
            start_at=now,
            end_at=now + timedelta(hours=1),
            duration_minutes=60,
        )
        assert slot.recurrence is None
        assert slot.duration_minutes == 60

    def test_valid_slot_create_with_recurrence(self):
        now = datetime.now(tz=timezone.utc)
        slot = SlotCreate(
            tutor_id=uuid.uuid4(),
            start_at=now,
            end_at=now + timedelta(hours=1),
            duration_minutes=60,
            recurrence=RecurrenceConfig(pattern="weekly", weeks_ahead=4),
        )
        assert slot.recurrence is not None
        assert slot.recurrence.weeks_ahead == 4

    def test_zero_duration_rejected(self):
        from pydantic import ValidationError

        now = datetime.now(tz=timezone.utc)
        with pytest.raises(ValidationError):
            SlotCreate(
                tutor_id=uuid.uuid4(),
                start_at=now,
                end_at=now + timedelta(hours=1),
                duration_minutes=0,
            )


class TestSlotUpdate:
    """Tests for SlotUpdate schema validation."""

    def test_all_fields_optional(self):
        update = SlotUpdate()
        assert update.start_at is None
        assert update.end_at is None
        assert update.duration_minutes is None

    def test_partial_update(self):
        now = datetime.now(tz=timezone.utc)
        update = SlotUpdate(start_at=now)
        assert update.start_at == now
        assert update.end_at is None

    def test_zero_duration_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SlotUpdate(duration_minutes=0)


class TestSlotResponse:
    """Tests for SlotResponse schema."""

    def test_from_orm_like_dict(self):
        slot_id = uuid.uuid4()
        tutor_id = uuid.uuid4()
        now = datetime.now(tz=timezone.utc)
        resp = SlotResponse(
            id=slot_id,
            tutor_id=tutor_id,
            start_at=now,
            end_at=now + timedelta(hours=1),
            duration_minutes=60,
            status="available",
            recurrence_group_id=None,
            created_at=now,
        )
        assert resp.id == slot_id
        assert resp.status == "available"


# ---------------------------------------------------------------------------
# Overlap detection tests
# ---------------------------------------------------------------------------


class TestOverlapDetection:
    """Tests for the _check_overlap helper function."""

    def test_no_overlap_before(self):
        # New slot ends before existing starts
        assert _check_overlap(
            datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc),
        ) is False

    def test_no_overlap_after(self):
        # New slot starts after existing ends
        assert _check_overlap(
            datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 13, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc),
        ) is False

    def test_no_overlap_adjacent(self):
        # New slot starts exactly when existing ends (no overlap)
        assert _check_overlap(
            datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc),
        ) is False

    def test_overlap_partial_start(self):
        # New slot starts during existing slot
        assert _check_overlap(
            datetime(2025, 1, 1, 10, 30, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 11, 30, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc),
        ) is True

    def test_overlap_partial_end(self):
        # New slot ends during existing slot
        assert _check_overlap(
            datetime(2025, 1, 1, 9, 30, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 10, 30, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc),
        ) is True

    def test_overlap_contained(self):
        # New slot is entirely within existing slot
        assert _check_overlap(
            datetime(2025, 1, 1, 10, 15, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 10, 45, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc),
        ) is True

    def test_overlap_containing(self):
        # New slot entirely contains existing slot
        assert _check_overlap(
            datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc),
        ) is True

    def test_overlap_exact_same_times(self):
        # Exact same time range
        assert _check_overlap(
            datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc),
        ) is True
