"""Tests for the notification service and reminder task."""
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# We need to mock settings before importing the module
import sys


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


class TestRenderTemplate:
    """Tests for template rendering."""

    def test_welcome_template_exists(self):
        """The welcome.html template file should exist."""
        templates_dir = Path(__file__).resolve().parent.parent / "app" / "templates"
        assert (templates_dir / "welcome.html").exists()

    def test_booking_confirmation_template_exists(self):
        """The booking_confirmation.html template file should exist."""
        templates_dir = Path(__file__).resolve().parent.parent / "app" / "templates"
        assert (templates_dir / "booking_confirmation.html").exists()

    def test_lesson_reminder_template_exists(self):
        """The lesson_reminder.html template file should exist."""
        templates_dir = Path(__file__).resolve().parent.parent / "app" / "templates"
        assert (templates_dir / "lesson_reminder.html").exists()

    def test_cancellation_template_exists(self):
        """The cancellation.html template file should exist."""
        templates_dir = Path(__file__).resolve().parent.parent / "app" / "templates"
        assert (templates_dir / "cancellation.html").exists()

    def test_post_lesson_template_exists(self):
        """The post_lesson.html template file should exist."""
        templates_dir = Path(__file__).resolve().parent.parent / "app" / "templates"
        assert (templates_dir / "post_lesson.html").exists()

    def test_password_reset_template_exists(self):
        """The password_reset.html template file should exist."""
        templates_dir = Path(__file__).resolve().parent.parent / "app" / "templates"
        assert (templates_dir / "password_reset.html").exists()

    def test_render_welcome_template(self):
        """Welcome template should substitute first_name."""
        from app.services.notification_service import _render_template

        html = _render_template("welcome", {"first_name": "Alice", "frontend_url": "http://localhost"})
        assert "Alice" in html
        assert "http://localhost" in html

    def test_render_booking_confirmation_template(self):
        """Booking confirmation template should substitute lesson details."""
        from app.services.notification_service import _render_template

        html = _render_template("booking_confirmation", {
            "lesson_date": "Monday, July 14, 2025",
            "lesson_time": "14:00 UTC",
            "lesson_url": "http://localhost/lessons/123",
        })
        assert "Monday, July 14, 2025" in html
        assert "14:00 UTC" in html
        assert "http://localhost/lessons/123" in html

    def test_render_cancellation_template(self):
        """Cancellation template should substitute reason and refund status."""
        from app.services.notification_service import _render_template

        html = _render_template("cancellation", {
            "cancellation_reason": "Student-initiated cancellation",
            "refund_status": "A full refund will be issued.",
            "frontend_url": "http://localhost",
        })
        assert "Student-initiated cancellation" in html
        assert "A full refund will be issued." in html

    def test_render_password_reset_template(self):
        """Password reset template should substitute token and expiry."""
        from app.services.notification_service import _render_template

        html = _render_template("password_reset", {
            "reset_token": "abc123token",
            "expires_minutes": "60",
            "frontend_url": "http://localhost",
        })
        assert "abc123token" in html
        assert "60" in html


class TestSendEmail:
    """Tests for the send_email function."""

    @pytest.mark.asyncio
    async def test_send_email_invalid_template_name(self):
        """send_email should log error and return for invalid template names."""
        from app.services.notification_service import send_email

        # Should not raise — just logs and returns
        await send_email("test@example.com", "nonexistent_template", {})

    @pytest.mark.asyncio
    async def test_send_email_success(self):
        """send_email should call resend.Emails.send on success."""
        from app.services import notification_service

        with patch.object(notification_service.resend.Emails, "send") as mock_send:
            mock_send.return_value = {"id": "email_123"}

            await notification_service.send_email(
                to="student@example.com",
                template_name="welcome",
                context={"first_name": "Bob", "frontend_url": "http://localhost"},
            )

            mock_send.assert_called_once()
            call_args = mock_send.call_args[0][0]
            assert call_args["to"] == ["student@example.com"]
            assert "Bob" in call_args["html"]

    @pytest.mark.asyncio
    async def test_send_email_retries_on_failure(self):
        """send_email should retry up to 3 times with backoff."""
        from app.services import notification_service

        sleep_calls = []

        async def fake_sleep(seconds):
            sleep_calls.append(seconds)

        with patch.object(notification_service.resend.Emails, "send") as mock_send:
            mock_send.side_effect = Exception("API error")

            with patch.object(notification_service.asyncio, "sleep", side_effect=fake_sleep):
                await notification_service.send_email(
                    to="student@example.com",
                    template_name="welcome",
                    context={"first_name": "Bob", "frontend_url": "http://localhost"},
                )

            # Should have been called 3 times (initial + 2 retries)
            assert mock_send.call_count == 3
            # Should have slept twice (between attempts)
            assert len(sleep_calls) == 2
            assert sleep_calls == [1, 2]

    @pytest.mark.asyncio
    async def test_send_email_succeeds_on_second_attempt(self):
        """send_email should succeed if the second attempt works."""
        from app.services import notification_service

        async def fake_sleep(seconds):
            pass

        with patch.object(notification_service.resend.Emails, "send") as mock_send:
            mock_send.side_effect = [Exception("Temporary error"), {"id": "email_123"}]

            with patch.object(notification_service.asyncio, "sleep", side_effect=fake_sleep):
                await notification_service.send_email(
                    to="student@example.com",
                    template_name="welcome",
                    context={"first_name": "Bob", "frontend_url": "http://localhost"},
                )

            assert mock_send.call_count == 2


class TestGetSubject:
    """Tests for the _get_subject helper."""

    def test_subject_for_each_template(self):
        """Each template should have a meaningful subject line."""
        from app.services.notification_service import _get_subject

        assert _get_subject("welcome", {}) == "Welcome to Fluency Tutoring!"
        assert _get_subject("booking_confirmation", {}) == "Your Lesson is Confirmed"
        assert _get_subject("lesson_reminder", {}) == "Reminder: Your Lesson is Tomorrow"
        assert _get_subject("cancellation", {}) == "Booking Cancellation Confirmation"
        assert _get_subject("post_lesson", {}) == "How Was Your Lesson?"
        assert _get_subject("password_reset", {}) == "Reset Your Password"

    def test_subject_for_unknown_template(self):
        """Unknown template names should return a generic subject."""
        from app.services.notification_service import _get_subject

        assert _get_subject("unknown", {}) == "Fluency Tutoring"
