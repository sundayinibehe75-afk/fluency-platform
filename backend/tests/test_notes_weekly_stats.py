"""Integration tests: profiles and time zones, lesson notes, weekly booking,
expiring-lesson reminders and the admin overview. Needs TEST_DATABASE_URL."""
import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from tests.test_booking_flow import (  # noqa: F401  (fixtures are used by name)
    _now,
    _slot,
    _tutor,
    _user,
    db,
    migrated_database,
    pytestmark,
)
from tests.test_plans_credits import _grant, _quiet


async def _weekly_slots(db, tutor, weeks, hours_from_now=48):
    return [await _slot(db, tutor, hours_from_now + 24 * 7 * w) for w in range(weeks)]


# ---------------------------------------------------------------------------
# Profile and time zones
# ---------------------------------------------------------------------------

async def test_time_formatting_uses_the_students_zone():
    from datetime import datetime, timezone

    from app.core import timefmt

    lesson = datetime(2026, 11, 9, 13, 0, tzinfo=timezone.utc)
    assert timefmt.lesson_time(lesson, "Africa/Lagos") == "14:00 (Africa/Lagos)"
    assert timefmt.lesson_time(lesson, "Europe/Berlin") == "14:00 (Europe/Berlin)"
    assert timefmt.lesson_time(lesson, "America/New_York") == "08:00 (America/New_York)"
    assert timefmt.lesson_time(lesson, "Not/AZone") == "13:00 (UTC)"
    assert timefmt.lesson_date(lesson, "Pacific/Auckland") == "Tuesday, November 10, 2026"


async def test_profile_rejects_unknown_time_zone():
    from app.schemas.users import ProfileUpdate

    assert ProfileUpdate(timezone="Africa/Lagos").timezone == "Africa/Lagos"
    with pytest.raises(ValidationError):
        ProfileUpdate(timezone="Mars/Olympus")
    with pytest.raises(ValidationError):
        ProfileUpdate(learning_goal="become famous")


async def test_register_saves_time_zone_and_goal(db):
    from app.models.user import User
    from app.schemas.auth import RegisterRequest
    from app.services import auth_service

    with patch("app.services.notification_service.send_email_later"):
        await auth_service.register_student(
            db,
            RegisterRequest(
                first_name="Lena", last_name="K", email="lena.tz@example.com",
                password="password123", timezone="Europe/Berlin", learning_goal="exam",
            ),
        )
    user = (await db.execute(select(User).where(User.email == "lena.tz@example.com"))).scalar_one()
    assert (user.timezone, user.learning_goal) == ("Europe/Berlin", "exam")


async def test_confirmation_email_shows_the_students_local_time(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    student.timezone = "America/New_York"
    await db.flush()
    slot = await _slot(db, tutor)
    with _quiet() as (email, _):
        await booking_service.create_booking(db, student.id, slot.id, "trial")
    assert email.call_args.kwargs["context"]["lesson_time"].endswith("(America/New_York)")


# ---------------------------------------------------------------------------
# Lesson notes
# ---------------------------------------------------------------------------

async def _taken_lesson(db):
    from app.services import booking_service

    admin, tutor = await _tutor(db)
    student = await _user(db)
    with _quiet():
        booking = await booking_service.create_booking(db, student.id, (await _slot(db, tutor)).id, "trial")
    return admin, student, booking


async def test_tutor_writes_notes_and_student_is_emailed_once(db):
    from app.services import notes_service

    admin, student, booking = await _taken_lesson(db)
    with patch("app.services.notification_service.send_email_later") as email:
        await notes_service.save_notes(
            db, booking.id, admin, "Talked about travel", "Write 5 sentences", "der Zug - train\ndie Reise - trip\n"
        )
        await notes_service.save_notes(
            db, booking.id, admin, "Talked about travel", "Write 6 sentences", "der Zug - train"
        )
    assert email.call_count == 1
    assert email.call_args.kwargs["template_name"] == "lesson_notes"
    assert email.call_args.kwargs["context"]["word_count"] == "2"

    notes = await notes_service.get_notes(db, booking.id, student)
    assert notes["homework"] == "Write 6 sentences"
    assert [n["booking_id"] for n in await notes_service.my_notes(db, student)] == [booking.id]


async def test_students_cannot_read_other_students_notes(db):
    from app.services import notes_service

    admin, _, booking = await _taken_lesson(db)
    with patch("app.services.notification_service.send_email_later"):
        await notes_service.save_notes(db, booking.id, admin, "Private", None, None)
    stranger = await _user(db)
    with pytest.raises(HTTPException) as exc:
        await notes_service.get_notes(db, booking.id, stranger)
    assert exc.value.status_code == 403


async def test_booking_list_shows_which_lessons_have_notes(db):
    from app.services import booking_service, notes_service

    admin, student, booking = await _taken_lesson(db)
    assert (await booking_service.list_bookings(db, student))[0].has_notes is False
    with patch("app.services.notification_service.send_email_later"):
        await notes_service.save_notes(db, booking.id, admin, "Good lesson", None, None)
    assert (await booking_service.list_bookings(db, student))[0].has_notes is True


# ---------------------------------------------------------------------------
# Weekly booking
# ---------------------------------------------------------------------------

async def test_weekly_booking_books_every_week_while_lessons_last(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    grant = await _grant(db, student, total=3, days=40)
    slots = await _weekly_slots(db, tutor, weeks=5)
    with _quiet() as (email, room):
        result = await booking_service.book_weekly(db, student, slots[0].id)
    assert [b.slot_id for b in result["booked"]] == [s.id for s in slots[:3]]  # 3 lessons only
    assert grant.used == 3
    assert room.await_count == 3
    assert email.call_count == 1  # one summary email, not one per lesson
    assert email.call_args.kwargs["template_name"] == "weekly_confirmation"


async def test_weekly_booking_skips_weeks_without_a_free_slot(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student, other = await _user(db), await _user(db)
    await _grant(db, student, total=8, days=40)
    await _grant(db, other, total=8, days=40)
    slots = await _weekly_slots(db, tutor, weeks=4)
    with _quiet():
        await booking_service.create_booking(db, other.id, slots[1].id, "plan")  # week 2 taken
        result = await booking_service.book_weekly(db, student, slots[0].id)
    booked = {b.slot_id for b in result["booked"]}
    assert booked == {slots[0].id, slots[2].id, slots[3].id}
    # week 2 is taken; later weeks have no slots yet; both are reported
    assert abs(result["skipped"][0] - slots[1].start_at) < timedelta(seconds=1)
    assert all(d > slots[3].start_at for d in result["skipped"][1:])


async def test_weekly_booking_stops_when_lessons_expire(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    await _grant(db, student, total=8, days=10)  # month ends in 10 days
    slots = await _weekly_slots(db, tutor, weeks=4)
    with _quiet():
        result = await booking_service.book_weekly(db, student, slots[0].id)
    assert len(result["booked"]) == 2  # day 2 and day 9; day 16 is after expiry


async def test_weekly_booking_needs_plan_lessons(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    with pytest.raises(HTTPException) as exc:
        await booking_service.book_weekly(db, student, (await _slot(db, tutor)).id)
    assert exc.value.detail["error"] == "NO_CREDITS"


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------

async def test_expiring_lessons_reminder_is_sent_once(db):
    from app.services import credit_service

    student = await _user(db)
    soon = await _grant(db, student, total=4, days=3)
    later = await _grant(db, student, total=4, days=20)
    with patch("app.services.notification_service.send_email_later") as email:
        await credit_service.send_expiry_reminders(db)
        await credit_service.send_expiry_reminders(db)
    mine = [c for c in email.call_args_list if c.kwargs["to"] == student.email]
    assert len(mine) == 1
    assert mine[0].kwargs["context"]["credits_left"] == "4"
    assert soon.expiry_reminder_sent_at is not None and later.expiry_reminder_sent_at is None


async def test_fully_booked_lessons_get_no_reminder(db):
    from app.services import credit_service

    student = await _user(db)
    grant = await _grant(db, student, total=2, days=3)
    grant.used = 2
    await db.flush()
    with patch("app.services.notification_service.send_email_later") as email:
        await credit_service.send_expiry_reminders(db)
    assert all(c.kwargs["to"] != student.email for c in email.call_args_list)


# ---------------------------------------------------------------------------
# Admin overview
# ---------------------------------------------------------------------------

async def test_admin_stats_count_income_plans_and_trials(db):
    from app.services import admin_service, payment_service

    admin, tutor = await _tutor(db)
    before = await admin_service.stats(db, admin)

    student = await _user(db)
    sub = {
        "id": "sub_stats", "status": "active", "customer": "cus_s", "cancel_at_period_end": False,
        "items": {"data": [{"current_period_end": int((_now() + timedelta(days=30)).timestamp())}]},
        "metadata": {"student_id": str(student.id), "product_key": "plan_3x"},
    }
    invoice = {
        "id": "in_stats", "amount_paid": 10800,
        "parent": {"subscription_details": {"subscription": "sub_stats"}},
        "lines": {"data": [{"period": {"end": int((_now() + timedelta(days=30)).timestamp())}}]},
    }
    body = json.dumps({"id": "evt_stats", "type": "invoice.paid", "data": {"object": invoice}}).encode()
    with patch("stripe.Webhook.construct_event"), patch("stripe.Subscription.retrieve", return_value=sub):
        await payment_service.handle_webhook(body, "sig", db)

    from app.services import booking_service

    with _quiet():
        await booking_service.create_booking(db, student.id, (await _slot(db, tutor)).id, "trial")

    after = await admin_service.stats(db, admin)
    assert after["income_this_month_cents"] - before["income_this_month_cents"] == 10800
    assert after["active_plans"] - before["active_plans"] == 1
    assert after["students"] - before["students"] == 1
    assert after["trials_this_month"] - before["trials_this_month"] == 1
    assert after["upcoming_next_7_days"] - before["upcoming_next_7_days"] == 1
    assert after["trial_to_plan"] - before["trial_to_plan"] == 1
