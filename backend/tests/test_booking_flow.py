"""Integration tests for bookings, payments, messaging and password reset.

These run against a real PostgreSQL database (set TEST_DATABASE_URL). The
schema is created with the real Alembic migrations, so the migrations are
tested too. External services (Stripe, Resend, Daily.co) are mocked.
"""
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not os.environ.get("TEST_DATABASE_URL"),
        reason="TEST_DATABASE_URL not set — integration tests need PostgreSQL",
    ),
]

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        check=True,
        capture_output=True,
        env={**os.environ, "DATABASE_URL": os.environ["TEST_DATABASE_URL"]},
    )


@pytest.fixture(scope="module", autouse=True)
def migrated_database():
    """Build the schema from scratch with the real migrations."""
    _alembic("downgrade", "base")
    _alembic("upgrade", "head")
    yield


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"], poolclass=NullPool)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    async with maker() as session:
        yield session
        await session.rollback()
    await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers to create test data
# ---------------------------------------------------------------------------

def _now():
    return datetime.now(tz=timezone.utc)


async def _user(db, role="student"):
    from app.models.user import User

    user = User(
        email=f"{uuid.uuid4().hex[:10]}@example.com",
        password_hash="x",
        first_name=role.title(),
        last_name="Test",
        role=role,
    )
    db.add(user)
    await db.flush()
    return user


async def _tutor(db):
    from app.models.tutor import Tutor

    admin = await _user(db, role="admin")
    tutor = Tutor(
        user_id=admin.id,
        display_name="Test Tutor",
        spoken_languages=["English"],
        specialisms=[],
        cefr_levels_taught=["A1"],
    )
    db.add(tutor)
    await db.flush()
    return admin, tutor


async def _slot(db, tutor, hours_from_now=48):
    from app.models.availability_slot import AvailabilitySlot

    start = _now() + timedelta(hours=hours_from_now)
    slot = AvailabilitySlot(
        tutor_id=tutor.id,
        start_at=start,
        end_at=start + timedelta(minutes=60),
        duration_minutes=60,
        status="available",
    )
    db.add(slot)
    await db.flush()
    return slot


async def _confirm(db, booking_id, payment_intent="pi_test"):
    """Mark a booking as paid, the way the Stripe webhook does."""
    from app.models.availability_slot import AvailabilitySlot
    from app.models.booking import Booking

    booking = (await db.execute(select(Booking).where(Booking.id == booking_id))).scalar_one()
    booking.status = "confirmed"
    booking.reserved_until = None
    booking.stripe_payment_intent_id = payment_intent
    slot = (await db.execute(select(AvailabilitySlot).where(AvailabilitySlot.id == booking.slot_id))).scalar_one()
    slot.status = "booked"
    await db.flush()
    return booking


# ---------------------------------------------------------------------------
# Bug 1 — cancelling someone else's booking
# ---------------------------------------------------------------------------

async def test_student_cannot_cancel_another_students_booking(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    owner, intruder = await _user(db), await _user(db)
    slot = await _slot(db, tutor)
    booking = await booking_service.create_booking(db, owner.id, slot.id)

    with patch("app.services.notification_service.send_email_later"):
        with pytest.raises(HTTPException) as exc:
            await booking_service.cancel_booking(db, booking.id, intruder)
    assert exc.value.status_code == 403


async def test_admin_can_cancel_any_booking(db):
    from app.services import booking_service

    admin, tutor = await _tutor(db)
    student = await _user(db)
    slot = await _slot(db, tutor)
    booking = await booking_service.create_booking(db, student.id, slot.id)

    with patch("app.services.notification_service.send_email_later"):
        await booking_service.cancel_booking(db, booking.id, admin)


async def test_cancelled_booking_cannot_be_cancelled_again(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    slot = await _slot(db, tutor)
    booking = await booking_service.create_booking(db, student.id, slot.id)
    with patch("app.services.notification_service.send_email_later"):
        await booking_service.cancel_booking(db, booking.id, student)
        with pytest.raises(HTTPException) as exc:
            await booking_service.cancel_booking(db, booking.id, student)
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Bug 2 — a freed slot can be booked again; never two active bookings
# ---------------------------------------------------------------------------

async def test_slot_can_be_rebooked_after_cancellation(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    first, second = await _user(db), await _user(db)
    slot = await _slot(db, tutor)

    booking = await booking_service.create_booking(db, first.id, slot.id)
    with patch("app.services.notification_service.send_email_later"):
        await booking_service.cancel_booking(db, booking.id, first)

    rebooked = await booking_service.create_booking(db, second.id, slot.id)
    assert rebooked.status == "pending_payment"


async def test_second_active_booking_on_same_slot_is_rejected(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    first, second = await _user(db), await _user(db)
    slot = await _slot(db, tutor)
    await booking_service.create_booking(db, first.id, slot.id)

    with pytest.raises(HTTPException) as exc:
        await booking_service.create_booking(db, second.id, slot.id)
    assert exc.value.status_code == 409


async def test_database_blocks_two_active_bookings_even_without_app_checks(db):
    """The partial unique index is the last line of defence against races."""
    from sqlalchemy.exc import IntegrityError

    from app.models.booking import Booking

    _, tutor = await _tutor(db)
    a, b = await _user(db), await _user(db)
    slot = await _slot(db, tutor)
    for student in (a, b):
        db.add(Booking(student_id=student.id, tutor_id=tutor.id, slot_id=slot.id,
                       status="pending_payment", price_cents=1000, currency="USD"))
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_past_slot_cannot_be_booked(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    slot = await _slot(db, tutor, hours_from_now=-2)

    with pytest.raises(HTTPException) as exc:
        await booking_service.create_booking(db, student.id, slot.id)
    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# Bug 3 — background jobs
# ---------------------------------------------------------------------------

async def test_expired_unpaid_booking_is_released_and_slot_rebookable(db):
    from app.models.booking import Booking
    from app.services import booking_service

    _, tutor = await _tutor(db)
    first, second = await _user(db), await _user(db)
    slot = await _slot(db, tutor)
    created = await booking_service.create_booking(db, first.id, slot.id)

    booking = (await db.execute(select(Booking).where(Booking.id == created.id))).scalar_one()
    booking.reserved_until = _now() - timedelta(minutes=1)
    await db.flush()

    assert await booking_service.expire_pending_bookings(db) >= 1
    await db.refresh(booking)
    assert booking.status == "cancelled"
    assert (await booking_service.create_booking(db, second.id, slot.id)).status == "pending_payment"


async def test_finished_lessons_are_marked_completed(db):
    from app.models.booking import Booking
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    slot = await _slot(db, tutor, hours_from_now=48)
    created = await booking_service.create_booking(db, student.id, slot.id)
    await _confirm(db, created.id)
    slot.start_at = _now() - timedelta(hours=2)
    slot.end_at = _now() - timedelta(hours=1)
    await db.flush()

    assert await booking_service.complete_finished_bookings(db) >= 1
    booking = (await db.execute(select(Booking).where(Booking.id == created.id))).scalar_one()
    assert booking.status == "completed"


# ---------------------------------------------------------------------------
# Bug 4 — webhook creates the video room and sends the confirmation email
# ---------------------------------------------------------------------------

def _webhook_body(booking_id, event_id=None):
    return json.dumps({
        "id": event_id or f"evt_{uuid.uuid4().hex}",
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": f"cs_{uuid.uuid4().hex}",
            "payment_intent": f"pi_{uuid.uuid4().hex}",
            "metadata": {"booking_id": str(booking_id)},
        }},
    }).encode()


async def test_webhook_confirms_booking_creates_room_and_emails(db):
    from app.models.booking import Booking
    from app.services import booking_service, payment_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    slot = await _slot(db, tutor)
    created = await booking_service.create_booking(db, student.id, slot.id)

    with patch("stripe.Webhook.construct_event"), \
         patch("app.services.video_service.create_room", new=AsyncMock()) as room, \
         patch("app.services.notification_service.send_email_later") as email:
        await payment_service.handle_webhook(_webhook_body(created.id), "sig", db)

    booking = (await db.execute(select(Booking).where(Booking.id == created.id))).scalar_one()
    assert booking.status == "confirmed"
    room.assert_awaited_once()
    assert email.call_args.kwargs["template_name"] == "booking_confirmation"


async def test_late_payment_for_taken_slot_is_refunded_not_double_booked(db):
    from app.models.booking import Booking
    from app.services import booking_service, payment_service

    _, tutor = await _tutor(db)
    late, other = await _user(db), await _user(db)
    slot = await _slot(db, tutor)
    created = await booking_service.create_booking(db, late.id, slot.id)
    booking = (await db.execute(select(Booking).where(Booking.id == created.id))).scalar_one()
    booking.reserved_until = _now() - timedelta(minutes=1)
    await db.flush()
    await booking_service.expire_pending_bookings(db)
    await booking_service.create_booking(db, other.id, slot.id)

    with patch("stripe.Webhook.construct_event"), \
         patch("app.services.payment_service.initiate_refund", new=AsyncMock(return_value=True)) as refund:
        await payment_service.handle_webhook(_webhook_body(created.id), "sig", db)

    await db.refresh(booking)
    assert booking.status == "cancelled"
    refund.assert_awaited_once()


async def test_checkout_rejected_after_reservation_expired(db):
    from app.models.booking import Booking
    from app.services import booking_service, payment_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    slot = await _slot(db, tutor)
    created = await booking_service.create_booking(db, student.id, slot.id)
    booking = (await db.execute(select(Booking).where(Booking.id == created.id))).scalar_one()
    booking.reserved_until = _now() - timedelta(minutes=1)
    await db.flush()

    with pytest.raises(HTTPException) as exc:
        await payment_service.create_checkout_session(db, created.id, student)
    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# Bug 8 — refunds follow the 12-hour rule
# ---------------------------------------------------------------------------

async def _paid_booking(db, hours_from_now):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    slot = await _slot(db, tutor, hours_from_now=hours_from_now)
    created = await booking_service.create_booking(db, student.id, slot.id)
    await _confirm(db, created.id)
    return student, created


async def test_paid_lesson_cancelled_with_enough_notice_is_refunded(db):
    from app.services import booking_service

    student, booking = await _paid_booking(db, hours_from_now=48)
    with patch("app.services.payment_service.initiate_refund", new=AsyncMock(return_value=True)) as refund, \
         patch("app.services.notification_service.send_email_later"):
        assert (await booking_service.cancel_booking(db, booking.id, student))["refund_issued"] is True
    refund.assert_awaited_once()


async def test_paid_lesson_cancelled_inside_12_hours_is_not_refunded(db):
    from app.services import booking_service

    student, booking = await _paid_booking(db, hours_from_now=6)
    with patch("app.services.payment_service.initiate_refund", new=AsyncMock(return_value=True)) as refund, \
         patch("app.services.notification_service.send_email_later"):
        assert (await booking_service.cancel_booking(db, booking.id, student))["refund_issued"] is False
    refund.assert_not_awaited()


async def test_admin_cancellation_is_always_refunded(db):
    from app.models.user import User
    from app.services import booking_service

    _, booking = await _paid_booking(db, hours_from_now=6)
    admin = (await db.execute(select(User).where(User.role == "admin"))).scalars().first()
    with patch("app.services.payment_service.initiate_refund", new=AsyncMock(return_value=True)) as refund, \
         patch("app.services.notification_service.send_email_later"):
        assert (await booking_service.cancel_booking(db, booking.id, admin))["refund_issued"] is True
    refund.assert_awaited_once()


# ---------------------------------------------------------------------------
# Bugs 5, 7 and slot removal
# ---------------------------------------------------------------------------

async def test_student_can_message_the_admin_tutor_and_back(db):
    from app.services.messaging_service import send_message

    admin, _ = await _tutor(db)
    student = await _user(db)
    await send_message(db, student.id, admin.id, "Hallo!")
    await send_message(db, admin.id, student.id, "Hallo zurück!")


async def test_password_reset_email_is_sent(db):
    from app.services import auth_service

    student = await _user(db)
    with patch("app.services.notification_service.send_email_later") as email:
        await auth_service.request_password_reset(db, student.email.upper())
    assert email.call_args.kwargs["template_name"] == "password_reset"
    assert email.call_args.kwargs["context"]["frontend_url"]


async def test_removing_slot_with_history_hides_it_instead_of_failing(db):
    from app.models.availability_slot import AvailabilitySlot
    from app.services import availability_service, booking_service

    admin, tutor = await _tutor(db)
    student = await _user(db)
    slot = await _slot(db, tutor)
    booking = await booking_service.create_booking(db, student.id, slot.id)
    with patch("app.services.notification_service.send_email_later"):
        await booking_service.cancel_booking(db, booking.id, student)
        await availability_service.delete_slot(db, slot.id, actor=admin)

    remaining = (await db.execute(select(AvailabilitySlot).where(AvailabilitySlot.id == slot.id))).scalar_one()
    assert remaining.status == "removed"


async def test_booking_list_reports_reviews(db):
    from app.models.review import Review
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    slot = await _slot(db, tutor)
    created = await booking_service.create_booking(db, student.id, slot.id)
    await _confirm(db, created.id)
    db.add(Review(booking_id=created.id, student_id=student.id, tutor_id=tutor.id, rating=5))
    await db.flush()

    listed = await booking_service.list_bookings(db, student)
    assert listed[0].has_review is True
