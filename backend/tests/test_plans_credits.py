"""Integration tests for the free trial, monthly plans, credits, rescheduling,
admin credit tools and time off. Needs TEST_DATABASE_URL (PostgreSQL)."""
import json
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
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


@contextmanager
def _quiet():
    """Mock email and video so confirmations don't call real services."""
    with patch("app.services.notification_service.send_email_later") as email, \
         patch("app.services.video_service.create_room", new=AsyncMock()) as room:
        yield email, room


async def _grant(db, student, total=8, days=30):
    from app.services import credit_service

    return await credit_service.grant_credits(
        db, student.id, total=total, expires_at=_now() + timedelta(days=days), source="admin"
    )


async def _booking(db, booking_id):
    from app.models.booking import Booking

    return (await db.execute(select(Booking).where(Booking.id == booking_id))).scalar_one()


# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------

async def test_migration_sets_new_prices(db):
    from app.services import subscription_service

    prices = {p["product_key"]: p for p in await subscription_service.list_prices(db)}
    assert prices["single_session"]["price_cents"] == 1000
    assert {k: (v["price_cents"], v["lessons_per_month"]) for k, v in prices.items() if v["is_plan"]} == {
        "plan_2x": (7600, 8),
        "plan_3x": (10800, 12),
        "plan_4x": (14000, 16),
        "plan_5x": (17000, 20),
    }
    assert "monthly_package" not in prices


async def test_single_lesson_costs_ten_dollars(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    created = await booking_service.create_booking(db, student.id, (await _slot(db, tutor)).id)
    assert created.price_cents == 1000
    assert created.status == "pending_payment"
    assert created.booking_type == "single"


# ---------------------------------------------------------------------------
# Free trial
# ---------------------------------------------------------------------------

async def test_free_trial_is_confirmed_and_only_once(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    with _quiet() as (email, room):
        trial = await booking_service.create_booking(db, student.id, (await _slot(db, tutor)).id, "trial")
    assert trial.status == "confirmed" and trial.price_cents == 0
    room.assert_awaited_once()

    with pytest.raises(HTTPException) as exc, _quiet():
        await booking_service.create_booking(db, student.id, (await _slot(db, tutor, 72)).id, "trial")
    assert exc.value.detail["error"] == "TRIAL_USED"


async def test_trial_cancelled_in_time_can_be_booked_again(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    with _quiet():
        trial = await booking_service.create_booking(db, student.id, (await _slot(db, tutor)).id, "trial")
        await booking_service.cancel_booking(db, trial.id, student)
        again = await booking_service.create_booking(db, student.id, (await _slot(db, tutor, 72)).id, "trial")
    assert again.status == "confirmed"


async def test_trial_cancelled_late_counts_as_used(db):
    from app.services import booking_service, credit_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    with _quiet():
        trial = await booking_service.create_booking(db, student.id, (await _slot(db, tutor, 6)).id, "trial")
        await booking_service.cancel_booking(db, trial.id, student)
    assert (await _booking(db, trial.id)).late_cancellation is True
    assert await credit_service.trial_available(db, student.id) is False


# ---------------------------------------------------------------------------
# Plan credits
# ---------------------------------------------------------------------------

async def test_plan_booking_needs_a_credit(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    with pytest.raises(HTTPException) as exc:
        await booking_service.create_booking(db, student.id, (await _slot(db, tutor)).id, "plan")
    assert exc.value.detail["error"] == "NO_CREDITS"


async def test_plan_booking_uses_one_credit_and_is_confirmed(db):
    from app.services import booking_service, credit_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    grant = await _grant(db, student, total=8)
    with _quiet():
        created = await booking_service.create_booking(db, student.id, (await _slot(db, tutor)).id, "plan")
    assert created.status == "confirmed" and created.price_cents == 0
    assert grant.used == 1
    assert (await credit_service.credit_summary(db, student.id))["credits_remaining"] == 7


async def test_credit_that_expires_before_the_lesson_cannot_be_used(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    await _grant(db, student, days=1)          # expires tomorrow
    slot = await _slot(db, tutor, hours_from_now=24 * 5)  # lesson in 5 days
    with pytest.raises(HTTPException) as exc:
        await booking_service.create_booking(db, student.id, slot.id, "plan")
    assert exc.value.detail["error"] == "NO_CREDITS"


async def test_soonest_expiring_credit_is_used_first(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    later = await _grant(db, student, days=40)
    sooner = await _grant(db, student, days=10)
    with _quiet():
        await booking_service.create_booking(db, student.id, (await _slot(db, tutor)).id, "plan")
    assert (sooner.used, later.used) == (1, 0)


async def test_plan_lesson_cancelled_in_time_returns_the_credit(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    grant = await _grant(db, student)
    with _quiet():
        created = await booking_service.create_booking(db, student.id, (await _slot(db, tutor)).id, "plan")
        result = await booking_service.cancel_booking(db, created.id, student)
    assert result == {"refund_issued": False, "credit_returned": True}
    assert grant.used == 0


async def test_plan_lesson_cancelled_late_keeps_the_credit_used(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    grant = await _grant(db, student)
    with _quiet():
        created = await booking_service.create_booking(db, student.id, (await _slot(db, tutor, 6)).id, "plan")
        result = await booking_service.cancel_booking(db, created.id, student)
    assert result["credit_returned"] is False
    assert grant.used == 1
    assert (await _booking(db, created.id)).late_cancellation is True


async def test_admin_cancel_always_returns_the_credit(db):
    from app.services import booking_service

    admin, tutor = await _tutor(db)
    student = await _user(db)
    grant = await _grant(db, student)
    with _quiet():
        created = await booking_service.create_booking(db, student.id, (await _slot(db, tutor, 6)).id, "plan")
        result = await booking_service.cancel_booking(db, created.id, admin)
    assert result["credit_returned"] is True and grant.used == 0


# ---------------------------------------------------------------------------
# Rescheduling
# ---------------------------------------------------------------------------

async def test_reschedule_moves_the_lesson(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    await _grant(db, student)
    old, new = await _slot(db, tutor, 48), await _slot(db, tutor, 72)
    with _quiet() as (email, room):
        created = await booking_service.create_booking(db, student.id, old.id, "plan")
        moved = await booking_service.reschedule_booking(db, created.id, new.id, student)
    assert moved.slot_id == new.id and moved.status == "confirmed"
    assert (old.status, new.status) == ("available", "booked")
    assert room.await_count == 2  # new room for the new time


async def test_reschedule_inside_12_hours_is_refused(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    await _grant(db, student)
    with _quiet():
        created = await booking_service.create_booking(db, student.id, (await _slot(db, tutor, 6)).id, "plan")
    with pytest.raises(HTTPException) as exc:
        await booking_service.reschedule_booking(db, created.id, (await _slot(db, tutor, 72)).id, student)
    assert exc.value.detail["error"] == "TOO_LATE"


async def test_reschedule_to_a_taken_slot_is_refused(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    a, b = await _user(db), await _user(db)
    await _grant(db, a)
    await _grant(db, b)
    s1, s2 = await _slot(db, tutor, 48), await _slot(db, tutor, 72)
    with _quiet():
        mine = await booking_service.create_booking(db, a.id, s1.id, "plan")
        await booking_service.create_booking(db, b.id, s2.id, "plan")
    with pytest.raises(HTTPException) as exc:
        await booking_service.reschedule_booking(db, mine.id, s2.id, a)
    assert exc.value.status_code == 409


async def test_reschedule_past_credit_expiry_is_refused(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    await _grant(db, student, days=4)
    with _quiet():
        created = await booking_service.create_booking(db, student.id, (await _slot(db, tutor, 48)).id, "plan")
    with pytest.raises(HTTPException) as exc:
        await booking_service.reschedule_booking(db, created.id, (await _slot(db, tutor, 24 * 6)).id, student)
    assert exc.value.detail["error"] == "CREDIT_EXPIRES"


# ---------------------------------------------------------------------------
# Subscriptions (Stripe mocked)
# ---------------------------------------------------------------------------

def _event(event_type, obj, event_id="evt_1"):
    return json.dumps({"id": event_id, "type": event_type, "data": {"object": obj}}).encode()


def _stripe_sub(student, sub_id="sub_1", status="active", cancel=False):
    end = int((_now() + timedelta(days=30)).timestamp())
    return {
        "id": sub_id,
        "status": status,
        "customer": "cus_1",
        "cancel_at_period_end": cancel,
        "items": {"data": [{"current_period_end": end}]},
        "metadata": {"student_id": str(student.id), "product_key": "plan_2x"},
    }


def _invoice(sub_id="sub_1", invoice_id="in_1"):
    end = int((_now() + timedelta(days=30)).timestamp())
    return {
        "id": invoice_id,
        "parent": {"subscription_details": {"subscription": sub_id}},
        "lines": {"data": [{"period": {"end": end}}]},
    }


async def test_paid_invoice_grants_monthly_credits_once(db):
    from app.services import payment_service, subscription_service

    student = await _user(db)
    with patch("stripe.Webhook.construct_event"), \
         patch("stripe.Subscription.retrieve", return_value=_stripe_sub(student)):
        await payment_service.handle_webhook(_event("invoice.paid", _invoice(), "evt_a"), "sig", db)
        await payment_service.handle_webhook(_event("invoice.paid", _invoice(), "evt_b"), "sig", db)

    info = await subscription_service.my_plan(db, student.id)
    assert info["plan"]["product_key"] == "plan_2x"
    assert info["plan"]["status"] == "active"
    assert info["credits_remaining"] == 8  # not 16: same invoice twice
    assert info["trial_available"] is True


async def test_new_month_adds_new_credits_and_old_ones_expire(db):
    from app.services import credit_service, payment_service

    student = await _user(db)
    with patch("stripe.Webhook.construct_event"), \
         patch("stripe.Subscription.retrieve", return_value=_stripe_sub(student, "sub_2")):
        await payment_service.handle_webhook(_event("invoice.paid", _invoice("sub_2", "in_m1"), "e1"), "s", db)
        await payment_service.handle_webhook(_event("invoice.paid", _invoice("sub_2", "in_m2"), "e2"), "s", db)
    assert (await credit_service.credit_summary(db, student.id))["credits_remaining"] == 16

    from app.models.credit_grant import CreditGrant

    grants = (await db.execute(select(CreditGrant).where(CreditGrant.student_id == student.id))).scalars().all()
    grants[0].expires_at = _now() - timedelta(minutes=1)  # first month ended
    await db.flush()
    assert (await credit_service.credit_summary(db, student.id))["credits_remaining"] == 8


async def test_cancel_plan_stops_renewal_but_keeps_credits(db):
    from app.services import payment_service, subscription_service

    student = await _user(db)
    with patch("stripe.Webhook.construct_event"), \
         patch("stripe.Subscription.retrieve", return_value=_stripe_sub(student, "sub_3")):
        await payment_service.handle_webhook(_event("invoice.paid", _invoice("sub_3", "in_3"), "e3"), "s", db)

    with patch("stripe.Subscription.modify") as modify:
        info = await subscription_service.cancel_subscription(db, student)
    modify.assert_called_once_with("sub_3", cancel_at_period_end=True)
    assert info["plan"]["cancel_at_period_end"] is True
    assert info["credits_remaining"] == 8

    # Month ends: Stripe deletes the subscription. Credits still last to period end.
    with patch("stripe.Webhook.construct_event"):
        await payment_service.handle_webhook(
            _event("customer.subscription.deleted", _stripe_sub(student, "sub_3", "canceled", True), "e4"), "s", db
        )
    info = await subscription_service.my_plan(db, student.id)
    assert info["plan"] is None
    assert info["credits_remaining"] == 8


async def test_cannot_buy_a_second_plan(db):
    from app.services import payment_service, subscription_service

    student = await _user(db)
    with patch("stripe.Webhook.construct_event"), \
         patch("stripe.Subscription.retrieve", return_value=_stripe_sub(student, "sub_4")):
        await payment_service.handle_webhook(_event("invoice.paid", _invoice("sub_4", "in_4"), "e5"), "s", db)
    with pytest.raises(HTTPException) as exc:
        await subscription_service.create_checkout(db, student, "plan_3x")
    assert exc.value.detail["error"] == "PLAN_EXISTS"


async def test_plan_checkout_is_a_monthly_subscription(db):
    from app.services import subscription_service

    student = await _user(db)
    with patch("stripe.checkout.Session.create", return_value=MagicMock(url="https://pay")) as create:
        result = await subscription_service.create_checkout(db, student, "plan_4x")
    kwargs = create.call_args.kwargs
    assert result == {"session_url": "https://pay"}
    assert kwargs["mode"] == "subscription"
    assert kwargs["line_items"][0]["price_data"]["unit_amount"] == 14000
    assert kwargs["line_items"][0]["price_data"]["recurring"] == {"interval": "month"}
    assert kwargs["subscription_data"]["metadata"]["student_id"] == str(student.id)


# ---------------------------------------------------------------------------
# Admin tools and time off
# ---------------------------------------------------------------------------

async def test_admin_adds_and_extends_credits(db):
    from app.services import admin_service, credit_service

    student = await _user(db)
    grant = await admin_service.add_credits(db, student.id, 3, _now() + timedelta(days=7), "Goodwill")
    assert grant["remaining"] == 3 and grant["source"] == "admin"

    new_expiry = _now() + timedelta(days=60)
    updated = await admin_service.update_grant(db, grant["id"], new_expiry, 2)
    assert updated["total"] == 5 and updated["expires_at"] == new_expiry
    assert (await credit_service.credit_summary(db, student.id))["credits_remaining"] == 5

    students = {s["id"]: s for s in await admin_service.list_students(db)}
    assert students[student.id]["credits_remaining"] == 5


async def test_admin_cannot_set_expiry_in_the_past(db):
    from app.services import admin_service

    student = await _user(db)
    with pytest.raises(HTTPException):
        await admin_service.add_credits(db, student.id, 1, _now() - timedelta(days=1), None)


async def test_time_off_blocks_free_slots_and_reports_booked_ones(db):
    from app.services import availability_service, booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    free, booked = await _slot(db, tutor, 48), await _slot(db, tutor, 50)
    outside = await _slot(db, tutor, 24 * 10)
    with _quiet():
        await booking_service.create_booking(db, student.id, booked.id, "trial")

    start, end = _now() + timedelta(hours=24), _now() + timedelta(hours=24 * 4)
    result = await availability_service.block_time(db, tutor.id, start, end)
    assert result == {"changed": 1, "booked_lessons_in_range": 1}
    assert (free.status, booked.status, outside.status) == ("blocked", "booked", "available")

    visible = {s.id for s in await availability_service.list_available_slots(db, tutor.id)}
    assert free.id not in visible and outside.id in visible

    with pytest.raises(HTTPException):
        await booking_service.create_booking(db, student.id, free.id)

    await availability_service.unblock_time(db, tutor.id, start, end)
    assert free.status == "available"


# ---------------------------------------------------------------------------
# Regression: a real (non-mocked) video room update must not break the reply
# ---------------------------------------------------------------------------

class _FakeDailyResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"url": "https://fluency.daily.co/test-room"}


class _FakeAsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, *args, **kwargs):
        return _FakeDailyResponse()


async def test_trial_booking_with_real_room_update_returns_cleanly(db):
    """Daily.co saving the room link updates the row (updated_at changes).
    Building the response afterwards used to fail with MissingGreenlet."""
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    with patch("app.services.video_service.httpx.AsyncClient", _FakeAsyncClient), \
         patch("app.services.notification_service.send_email_later"):
        created = await booking_service.create_booking(db, student.id, (await _slot(db, tutor)).id, "trial")
    assert created.status == "confirmed"
    assert created.video_room_url == "https://fluency.daily.co/test-room"


async def test_deleted_slot_time_can_be_used_again(db):
    """A slot with booking history is kept as 'removed' when deleted; it must
    not block creating a new slot at the same time."""
    from app.schemas.availability import SlotCreate
    from app.services import availability_service, booking_service

    admin, tutor = await _tutor(db)
    student = await _user(db)
    old = await _slot(db, tutor, hours_from_now=30)
    with _quiet():
        trial = await booking_service.create_booking(db, student.id, old.id, "trial")
        await booking_service.cancel_booking(db, trial.id, student)
        await availability_service.delete_slot(db, old.id, actor=admin)
    assert old.status == "removed"

    created = await availability_service.create_slots(
        db,
        SlotCreate(tutor_id=tutor.id, start_at=old.start_at, end_at=old.end_at, duration_minutes=60),
    )
    assert len(created) == 1 and created[0].status == "available"
