"""Unit tests for reviews schemas, service logic, and router.

Tests cover:
- Schema validation (ReviewCreate, ReviewResponse, ReviewVisibilityUpdate)
- Service logic (submit_review validations, set_visibility, list_reviews)
- Using mocked DB sessions for service-level tests
"""
import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.schemas.reviews import ReviewCreate, ReviewResponse, ReviewVisibilityUpdate


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestReviewCreate:
    """Tests for ReviewCreate schema validation."""

    def test_valid_review_create(self):
        review = ReviewCreate(
            booking_id=uuid.uuid4(),
            rating=5,
            comment="Great lesson!",
        )
        assert review.rating == 5
        assert review.comment == "Great lesson!"

    def test_valid_review_without_comment(self):
        review = ReviewCreate(
            booking_id=uuid.uuid4(),
            rating=3,
        )
        assert review.comment is None

    def test_rating_min_boundary(self):
        review = ReviewCreate(
            booking_id=uuid.uuid4(),
            rating=1,
        )
        assert review.rating == 1

    def test_rating_max_boundary(self):
        review = ReviewCreate(
            booking_id=uuid.uuid4(),
            rating=5,
        )
        assert review.rating == 5

    def test_rating_below_min_rejected(self):
        with pytest.raises(ValidationError):
            ReviewCreate(
                booking_id=uuid.uuid4(),
                rating=0,
            )

    def test_rating_above_max_rejected(self):
        with pytest.raises(ValidationError):
            ReviewCreate(
                booking_id=uuid.uuid4(),
                rating=6,
            )

    def test_comment_max_length_accepted(self):
        comment = "a" * 1000
        review = ReviewCreate(
            booking_id=uuid.uuid4(),
            rating=4,
            comment=comment,
        )
        assert len(review.comment) == 1000

    def test_comment_exceeds_max_length_rejected(self):
        comment = "a" * 1001
        with pytest.raises(ValidationError):
            ReviewCreate(
                booking_id=uuid.uuid4(),
                rating=4,
                comment=comment,
            )

    def test_missing_booking_id_rejected(self):
        with pytest.raises(ValidationError):
            ReviewCreate(rating=4)  # type: ignore[call-arg]

    def test_missing_rating_rejected(self):
        with pytest.raises(ValidationError):
            ReviewCreate(booking_id=uuid.uuid4())  # type: ignore[call-arg]


class TestReviewResponse:
    """Tests for ReviewResponse schema."""

    def test_valid_review_response(self):
        now = datetime.now(tz=timezone.utc)
        resp = ReviewResponse(
            id=uuid.uuid4(),
            booking_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            tutor_id=uuid.uuid4(),
            rating=4,
            comment="Good session",
            is_hidden=False,
            submitted_at=now,
        )
        assert resp.rating == 4
        assert resp.is_hidden is False

    def test_from_attributes_mode(self):
        """Verify from_attributes (ORM mode) works."""
        now = datetime.now(tz=timezone.utc)
        review_id = uuid.uuid4()

        class FakeReview:
            id = review_id
            booking_id = uuid.uuid4()
            student_id = uuid.uuid4()
            tutor_id = uuid.uuid4()
            rating = 5
            comment = "Excellent!"
            is_hidden = False
            submitted_at = now

        resp = ReviewResponse.model_validate(FakeReview())
        assert resp.id == review_id
        assert resp.rating == 5

    def test_comment_can_be_none(self):
        now = datetime.now(tz=timezone.utc)
        resp = ReviewResponse(
            id=uuid.uuid4(),
            booking_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            tutor_id=uuid.uuid4(),
            rating=3,
            comment=None,
            is_hidden=False,
            submitted_at=now,
        )
        assert resp.comment is None


class TestReviewVisibilityUpdate:
    """Tests for ReviewVisibilityUpdate schema."""

    def test_hide_review(self):
        update = ReviewVisibilityUpdate(is_hidden=True)
        assert update.is_hidden is True

    def test_unhide_review(self):
        update = ReviewVisibilityUpdate(is_hidden=False)
        assert update.is_hidden is False

    def test_missing_is_hidden_rejected(self):
        with pytest.raises(ValidationError):
            ReviewVisibilityUpdate()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Service logic tests (using mocked DB)
# ---------------------------------------------------------------------------


class TestSubmitReview:
    """Tests for submit_review service logic."""

    def test_booking_not_found_raises_404(self):
        """Non-existent booking should raise 404."""
        from fastapi import HTTPException

        from app.services.review_service import submit_review

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(submit_review(db, uuid.uuid4(), uuid.uuid4(), 5))

        assert exc_info.value.status_code == 404

    def test_booking_not_owned_by_student_raises_403(self):
        """Booking belonging to another student should raise 403."""
        from fastapi import HTTPException

        from app.services.review_service import submit_review

        booking_id = uuid.uuid4()
        student_id = uuid.uuid4()
        other_student_id = uuid.uuid4()

        mock_booking = MagicMock()
        mock_booking.id = booking_id
        mock_booking.student_id = other_student_id
        mock_booking.status = "completed"

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_booking
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(submit_review(db, booking_id, student_id, 4))

        assert exc_info.value.status_code == 403

    def test_booking_not_completed_raises_403(self):
        """Booking that is not completed should raise 403."""
        from fastapi import HTTPException

        from app.services.review_service import submit_review

        booking_id = uuid.uuid4()
        student_id = uuid.uuid4()

        mock_booking = MagicMock()
        mock_booking.id = booking_id
        mock_booking.student_id = student_id
        mock_booking.status = "confirmed"

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_booking
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(submit_review(db, booking_id, student_id, 4))

        assert exc_info.value.status_code == 403
        assert "completed" in exc_info.value.detail["detail"].lower()

    def test_duplicate_review_raises_409(self):
        """Submitting a second review for the same booking should raise 409."""
        from fastapi import HTTPException

        from app.services.review_service import submit_review

        booking_id = uuid.uuid4()
        student_id = uuid.uuid4()
        tutor_id = uuid.uuid4()

        mock_booking = MagicMock()
        mock_booking.id = booking_id
        mock_booking.student_id = student_id
        mock_booking.tutor_id = tutor_id
        mock_booking.status = "completed"

        mock_existing_review = MagicMock()

        db = AsyncMock()
        # First call returns booking, second call returns existing review
        booking_result = MagicMock()
        booking_result.scalar_one_or_none.return_value = mock_booking
        review_result = MagicMock()
        review_result.scalar_one_or_none.return_value = mock_existing_review
        db.execute = AsyncMock(side_effect=[booking_result, review_result])

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(submit_review(db, booking_id, student_id, 5))

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["error"] == "REVIEW_EXISTS"

    def test_successful_review_submission(self):
        """A valid review submission should succeed and call recalculate."""
        from app.services.review_service import submit_review

        booking_id = uuid.uuid4()
        student_id = uuid.uuid4()
        tutor_id = uuid.uuid4()
        now = datetime.now(tz=timezone.utc)

        mock_booking = MagicMock()
        mock_booking.id = booking_id
        mock_booking.student_id = student_id
        mock_booking.tutor_id = tutor_id
        mock_booking.status = "completed"

        db = AsyncMock()
        # Calls: 1) get booking, 2) check existing review
        booking_result = MagicMock()
        booking_result.scalar_one_or_none.return_value = mock_booking
        no_review_result = MagicMock()
        no_review_result.scalar_one_or_none.return_value = None

        db.execute = AsyncMock(
            side_effect=[booking_result, no_review_result]
        )
        db.add = MagicMock()
        db.flush = AsyncMock()

        # Patch _recalculate_tutor_rating and ReviewResponse.model_validate
        with patch("app.services.review_service._recalculate_tutor_rating", new_callable=AsyncMock) as mock_recalc:
            with patch("app.services.review_service.ReviewResponse") as MockResp:
                mock_response = MagicMock()
                MockResp.model_validate.return_value = mock_response
                result = asyncio.run(
                    submit_review(db, booking_id, student_id, 5, "Excellent!")
                )

        # Verify the review was added to the session
        assert db.add.called
        added_review = db.add.call_args[0][0]
        assert added_review.rating == 5
        assert added_review.comment == "Excellent!"
        assert added_review.booking_id == booking_id
        assert added_review.student_id == student_id
        assert added_review.tutor_id == tutor_id
        # Verify recalculate was called with the tutor_id
        mock_recalc.assert_called_once_with(db, tutor_id)
        assert result == mock_response


class TestSetVisibility:
    """Tests for set_visibility service logic."""

    def test_review_not_found_raises_404(self):
        """Non-existent review should raise 404."""
        from fastapi import HTTPException

        from app.services.review_service import set_visibility

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(set_visibility(db, uuid.uuid4(), True))

        assert exc_info.value.status_code == 404

    def test_hide_review_success(self):
        """Hiding a review should update is_hidden and recalculate rating."""
        from app.services.review_service import set_visibility

        review_id = uuid.uuid4()
        tutor_id = uuid.uuid4()
        now = datetime.now(tz=timezone.utc)

        mock_review = MagicMock()
        mock_review.id = review_id
        mock_review.booking_id = uuid.uuid4()
        mock_review.student_id = uuid.uuid4()
        mock_review.tutor_id = tutor_id
        mock_review.rating = 3
        mock_review.comment = "OK"
        mock_review.is_hidden = False
        mock_review.submitted_at = now

        mock_tutor = MagicMock()
        mock_tutor.avg_rating = 3.0
        mock_tutor.review_count = 1

        # After hiding, no visible reviews
        mock_agg_row = MagicMock()
        mock_agg_row.cnt = 0
        mock_agg_row.avg = None
        mock_agg_result = MagicMock()
        mock_agg_result.one.return_value = mock_agg_row

        mock_tutor_result = MagicMock()
        mock_tutor_result.scalar_one_or_none.return_value = mock_tutor

        db = AsyncMock()
        review_result = MagicMock()
        review_result.scalar_one_or_none.return_value = mock_review
        db.execute = AsyncMock(
            side_effect=[review_result, mock_agg_result, mock_tutor_result]
        )
        db.flush = AsyncMock()

        result = asyncio.run(set_visibility(db, review_id, True))

        assert mock_review.is_hidden is True
        assert mock_tutor.avg_rating == 0.0
        assert mock_tutor.review_count == 0
