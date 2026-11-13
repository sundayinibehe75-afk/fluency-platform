"""Integration tests for Paystack payments (API calls mocked).
Needs TEST_DATABASE_URL (PostgreSQL)."""
import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

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
from tests.test_plans_credits import _quiet

SECRET = "sk_test_fake_secret"


@pytest.fixture(autouse=True)
def _paystack_settings():
    from app.core.config import settings

    old = (settings.payment_provider, settings.paystack_secret_key)
    settings.payment_provider, settings.paystack_secret_key = "paystack", SECRET
    yield
    settings.payment_provider, settings.paystack_secret_key = old


@pytest.fixture(autouse=True)
def _no_live_rate():
    """No network in tests: the live feed is 'down' unless a test says otherwise."""
    with patch("app.services.paystack_service._fetch_live_rate", AsyncMock(return_value=None)) as fake:
        yield fake


def _signed(event: dict) -> tuple[bytes, str]:
    raw = json.dumps(event).encode()
    return raw, hmac.new(SECRET.encode(), raw, hashlib.sha512).hexdigest()


async def _pending_booking(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    created = await booking_service.create_booking(db, student.id, (await _slot(db, tutor)).id)
    from app.models.booking import Booking

    return student, (await db.execute(select(Booking).where(Booking.id == created.id))).scalar_one()


async def test_checkout_needs_an_exchange_rate(db):
    from app.services import paystack_service

    student, booking = await _pending_booking(db)
    from app.models.app_setting import AppSetting

    await db.execute(AppSetting.__table__.delete())
    with pytest.raises(HTTPException) as exc:
        await paystack_service.start_booking_payment(db, booking, student)
    assert exc.value.detail["error"] == "PAYMENTS_NOT_READY"


async def test_single_lesson_is_charged_in_naira_at_the_admin_rate(db):
    from app.services import paystack_service

    await paystack_service.set_rate(db, Decimal("1500"))
    student, booking = await _pending_booking(db)
    api = AsyncMock(return_value={"authorization_url": "https://checkout.paystack.com/abc"})
    with patch("app.services.paystack_service._api", api):
        url = await paystack_service.start_booking_payment(db, booking, student)
    body = api.call_args.args[2]
    assert url == "https://checkout.paystack.com/abc"
    assert body["amount"] == 1_500_000  # $10 x 1500 = N15,000 = 1,500,000 kobo
    assert body["currency"] == "NGN"
    assert body["metadata"]["kind"] == "booking"
    assert booking.payment_provider == "paystack"
    assert booking.payment_reference == body["reference"]


async def test_webhook_rejects_a_bad_signature(db):
    from app.services import paystack_service

    raw, _ = _signed({"event": "charge.success", "data": {}})
    with pytest.raises(HTTPException) as exc:
        await paystack_service.handle_webhook(db, raw, "not-the-signature")
    assert exc.value.status_code == 400


async def test_paid_booking_is_confirmed_once(db):
    from app.models.payment import Payment
    from app.services import paystack_service

    await paystack_service.set_rate(db, Decimal("1500"))
    student, booking = await _pending_booking(db)
    booking.payment_provider, booking.payment_reference = "paystack", "fg_bk_test_ref1"
    await db.flush()
    event = {"event": "charge.success", "data": {
        "status": "success", "reference": "fg_bk_test_ref1", "metadata": {"kind": "booking"}}}
    raw, sig = _signed(event)
    with _quiet():
        first = await paystack_service.handle_webhook(db, raw, sig)
        second = await paystack_service.handle_webhook(db, raw, sig)
    assert (first["status"], second["status"]) == ("booking_confirmed", "already_processed")
    assert booking.status == "confirmed"
    payments = (await db.execute(select(Payment).where(Payment.booking_id == booking.id))).scalars().all()
    assert len(payments) == 1 and payments[0].amount_cents == 1000


async def test_package_grants_monthly_lessons_once(db):
    from app.services import credit_service, paystack_service

    student = await _user(db)
    data = {"status": "success", "reference": "fg_pk_test_ref2",
            "metadata": {"kind": "package", "student_id": str(student.id), "product_key": "plan_3x"}}
    assert await paystack_service.process_successful_charge(db, data) == "package_granted"
    assert await paystack_service.process_successful_charge(db, data) == "already_processed"
    summary = await credit_service.credit_summary(db, student.id)
    assert summary["credits_remaining"] == 12
    assert timedelta(days=29) < summary["credits_expire_at"] - _now() <= timedelta(days=30)


async def test_failed_charge_changes_nothing(db):
    from app.services import credit_service, paystack_service

    student = await _user(db)
    data = {"status": "failed", "reference": "fg_pk_test_ref3",
            "metadata": {"kind": "package", "student_id": str(student.id), "product_key": "plan_2x"}}
    assert await paystack_service.process_successful_charge(db, data) == "ignored"
    assert (await credit_service.credit_summary(db, student.id))["credits_remaining"] == 0


async def test_verify_only_for_the_payer(db):
    from app.services import paystack_service

    student = await _user(db)
    stranger = await _user(db)
    data = {"status": "success", "reference": "fg_pk_test_ref4",
            "metadata": {"kind": "package", "student_id": str(student.id), "product_key": "plan_2x"}}
    with patch("app.services.paystack_service._api", AsyncMock(return_value=data)):
        with pytest.raises(HTTPException) as exc:
            await paystack_service.verify_and_process(db, "fg_pk_test_ref4", stranger)
        assert exc.value.status_code == 403
        result = await paystack_service.verify_and_process(db, "fg_pk_test_ref4", student)
    assert result["result"] == "package_granted"


async def test_cancel_in_time_refunds_through_paystack(db):
    from app.services import booking_service, paystack_service

    student, booking = await _pending_booking(db)
    booking.payment_provider, booking.payment_reference = "paystack", "fg_bk_test_ref5"
    await db.flush()
    with _quiet():
        await paystack_service.process_successful_charge(
            db, {"status": "success", "reference": "fg_bk_test_ref5", "metadata": {"kind": "booking"}})
    api = AsyncMock(return_value={})
    with patch("app.services.paystack_service._api", api), _quiet():
        result = await booking_service.cancel_booking(db, booking.id, student)
    assert result["refund_issued"] is True
    assert api.call_args.args[1:] == ("/refund", {"transaction": "fg_bk_test_ref5"})


async def test_package_checkout_uses_paystack(db):
    from app.services import paystack_service, subscription_service

    await paystack_service.set_rate(db, Decimal("1600"))
    student = await _user(db)
    api = AsyncMock(return_value={"authorization_url": "https://checkout.paystack.com/pk"})
    with patch("app.services.paystack_service._api", api):
        result = await subscription_service.create_checkout(db, student, "plan_2x")
    assert result == {"session_url": "https://checkout.paystack.com/pk"}
    assert api.call_args.args[2]["amount"] == 7600 * 1600  # $76 at N1600/$


async def test_live_rate_with_markup_is_used_and_cached(db, _no_live_rate):
    from app.services import paystack_service

    await paystack_service.set_rate(db, Decimal("1400"))  # backup, should be ignored
    await paystack_service.set_markup(db, Decimal("2"))
    _no_live_rate.return_value = Decimal("1500")

    info = await paystack_service.get_rate_info(db)
    assert info["source"] == "live"
    assert info["rate"] == Decimal("1530.00")  # 1500 + 2%
    await paystack_service.get_rate_info(db)
    assert _no_live_rate.await_count == 1  # cached, not fetched again

    student, booking = await _pending_booking(db)
    with patch.object(paystack_service, "_api", AsyncMock(return_value={"authorization_url": "https://pay"})) as api:
        await paystack_service.start_booking_payment(db, booking, student)
    assert api.call_args.args[2]["amount"] == booking.price_cents * 1530


async def test_falls_back_to_backup_when_live_rate_is_too_old(db, _no_live_rate):
    from datetime import datetime, timezone

    from app.services import paystack_service

    await paystack_service.set_rate(db, Decimal("1450"))
    old = datetime.now(timezone.utc) - paystack_service.LIVE_MAX_AGE - timedelta(hours=1)
    await paystack_service._put_setting(db, paystack_service.LIVE_KEY, "1500")
    await paystack_service._put_setting(db, paystack_service.LIVE_AT_KEY, old.isoformat())

    info = await paystack_service.get_rate_info(db)  # feed is down (returns None)
    assert _no_live_rate.await_count == 1
    assert (info["source"], info["rate"]) == ("backup", Decimal("1450"))


async def test_markup_must_be_reasonable(db):
    from app.services import paystack_service

    with pytest.raises(HTTPException):
        await paystack_service.set_markup(db, Decimal("50"))


async def test_student_can_go_back_to_payment_after_closing_the_page(db):
    from app.models.booking import Booking
    from app.services import booking_service, paystack_service

    await paystack_service.set_rate(db, Decimal("1500"))
    student, booking = await _pending_booking(db)

    again = await booking_service.create_booking(db, student.id, booking.slot_id)
    assert again.id == booking.id and again.status == "pending_payment"

    active = (
        await db.execute(select(Booking).where(Booking.slot_id == booking.slot_id, Booking.status == "pending_payment"))
    ).scalars().all()
    assert len(active) == 1


async def test_payment_from_an_earlier_attempt_still_confirms_and_a_second_is_refunded(db):
    from app.models.payment import Payment
    from app.services import paystack_service

    await paystack_service.set_rate(db, Decimal("1500"))
    student, booking = await _pending_booking(db)
    with patch.object(paystack_service, "_api", AsyncMock(return_value={"authorization_url": "https://pay"})):
        await paystack_service.start_booking_payment(db, booking, student)
        first_ref = booking.payment_reference
        await paystack_service.start_booking_payment(db, booking, student)  # student came back
        second_ref = booking.payment_reference
    assert first_ref != second_ref

    meta = {"kind": "booking", "booking_id": str(booking.id)}
    with _quiet():
        result = await paystack_service.process_successful_charge(
            db, {"status": "success", "reference": first_ref, "metadata": meta}
        )
    assert result == "booking_confirmed"
    await db.refresh(booking)
    assert booking.status == "confirmed" and booking.payment_reference == first_ref

    with patch.object(paystack_service, "refund", AsyncMock()) as refund:
        result = await paystack_service.process_successful_charge(
            db, {"status": "success", "reference": second_ref, "metadata": meta}
        )
    assert result == "already_processed"
    refund.assert_awaited_once_with(second_ref)
    statuses = sorted(
        (await db.execute(select(Payment.status).where(Payment.booking_id == booking.id))).scalars().all()
    )
    assert statuses == ["duplicate", "succeeded"]


# ---------------------------------------------------------------------------
# Automatic renewal
# ---------------------------------------------------------------------------

REUSABLE_CARD = {"authorization_code": "AUTH_test123", "reusable": True, "brand": "visa", "last4": "4081"}


async def _auto_plan(db, student, reference="fg_pk_auto_1"):
    """Student buys plan_2x with 'Renew automatically' ticked; returns the Subscription."""
    from app.models.subscription import Subscription
    from app.services import paystack_service

    meta = {"kind": "package", "student_id": str(student.id), "product_key": "plan_2x", "auto_renew": True}
    assert await paystack_service.process_successful_charge(
        db, {"status": "success", "reference": reference, "metadata": meta, "authorization": REUSABLE_CARD}
    ) == "package_granted"
    return (await db.execute(select(Subscription).where(Subscription.student_id == student.id))).scalar_one()


async def _make_due(db, sub, days_ago=0):
    from datetime import datetime, timezone

    sub.current_period_end = datetime.now(timezone.utc) - timedelta(days=days_ago, minutes=1)
    sub.reminder_sent_for = sub.current_period_end
    await db.flush()


async def test_auto_renew_purchase_saves_the_card_and_shows_on_the_dashboard(db):
    from app.services import subscription_service

    student = await _user(db)
    sub = await _auto_plan(db, student)
    assert (sub.provider, sub.status, sub.card_label) == ("paystack", "active", "Visa ending 4081")
    assert sub.paystack_authorization_code == "AUTH_test123"

    info = await subscription_service.my_plan(db, student.id)
    assert info["plan"]["product_key"] == "plan_2x" and info["plan"]["card_label"] == "Visa ending 4081"
    assert info["plan"]["cancel_at_period_end"] is False


async def test_package_without_auto_renew_or_reusable_card_does_not_renew(db):
    from app.models.subscription import Subscription
    from app.services import paystack_service

    student = await _user(db)
    for ref, auto, card in (("fg_pk_once", False, REUSABLE_CARD), ("fg_pk_bank", True, {"reusable": False})):
        meta = {"kind": "package", "student_id": str(student.id), "product_key": "plan_2x", "auto_renew": auto}
        await paystack_service.process_successful_charge(
            db, {"status": "success", "reference": ref, "metadata": meta, "authorization": card}
        )
    assert (await db.execute(select(Subscription).where(Subscription.student_id == student.id))).first() is None


async def test_second_auto_renewing_plan_is_refused(db):
    from app.services import paystack_service, subscription_service

    await paystack_service.set_rate(db, Decimal("1500"))
    student = await _user(db)
    await _auto_plan(db, student)
    with pytest.raises(HTTPException) as exc:
        await subscription_service.create_checkout(db, student, "plan_3x", auto_renew=True)
    assert exc.value.detail["error"] == "PLAN_EXISTS"
    # Buying an extra month without renewal is still fine
    with patch.object(paystack_service, "_api", AsyncMock(return_value={"authorization_url": "https://pay"})):
        await subscription_service.create_checkout(db, student, "plan_3x", auto_renew=False)


async def test_due_plan_is_charged_and_continues_without_a_gap(db):
    from app.models.credit_grant import CreditGrant
    from app.services import paystack_service

    await paystack_service.set_rate(db, Decimal("1500"))
    student = await _user(db)
    sub = await _auto_plan(db, student)
    await _make_due(db, sub)
    old_end = sub.current_period_end

    charge = AsyncMock(return_value={"status": "success", "authorization": REUSABLE_CARD})
    with patch.object(paystack_service, "_api", charge), _quiet() as (email, _):
        assert await paystack_service.renew_due_plans(db) == 1
    path, body = charge.call_args.args[1:]
    assert path == "/transaction/charge_authorization"
    assert body["authorization_code"] == "AUTH_test123" and body["amount"] == 7600 * 1500

    grants = (await db.execute(select(CreditGrant).where(CreditGrant.student_id == student.id))).scalars().all()
    assert len(grants) == 2
    renewal = next(g for g in grants if g.payment_reference.startswith("fg_rn_"))
    assert renewal.expires_at == old_end + timedelta(days=paystack_service.PACKAGE_DAYS)
    assert sub.current_period_end == renewal.expires_at and sub.status == "active"
    assert email.call_args.kwargs["context"]["subject"] == "Your plan has renewed"

    # Not due any more: running again charges nothing
    with patch.object(paystack_service, "_api", charge):
        assert await paystack_service.renew_due_plans(db) == 0
    assert charge.await_count == 1


async def test_failed_renewal_retries_daily_then_stops(db):
    from app.services import paystack_service

    await paystack_service.set_rate(db, Decimal("1500"))
    student = await _user(db)
    sub = await _auto_plan(db, student)
    await _make_due(db, sub)

    declined = AsyncMock(return_value={"status": "failed", "gateway_response": "Insufficient Funds"})
    subjects = []
    for attempt in range(1, 4):
        with patch.object(paystack_service, "_api", declined), _quiet() as (email, _):
            await paystack_service.renew_due_plans(db)
            await paystack_service.renew_due_plans(db)  # same day: no second charge
        subjects.append(email.call_args.kwargs["context"]["subject"])
        assert declined.await_count == attempt
        sub.last_charge_attempt_at -= paystack_service.RETRY_AFTER  # a day passes

    assert sub.status == "canceled" and sub.renewal_failures == 3
    assert subjects == ["Your plan renewal payment failed"] * 2 + ["Your plan has stopped"]


async def test_turned_off_plan_is_never_charged_and_ends(db):
    from app.services import paystack_service, subscription_service

    student = await _user(db)
    sub = await _auto_plan(db, student)
    info = await subscription_service.cancel_subscription(db, student)
    assert info["plan"]["cancel_at_period_end"] is True
    await _make_due(db, sub)

    api = AsyncMock()
    with patch.object(paystack_service, "_api", api):
        await paystack_service.renew_due_plans(db)
    api.assert_not_awaited()
    assert sub.status == "canceled"
    with pytest.raises(HTTPException):
        await subscription_service.resume_subscription(db, student)  # no live plan any more


async def test_reminder_is_sent_once_before_renewal(db):
    from datetime import datetime, timezone

    from app.services import paystack_service

    await paystack_service.set_rate(db, Decimal("1500"))
    student = await _user(db)
    sub = await _auto_plan(db, student)
    sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=2)
    await db.flush()

    with patch.object(paystack_service, "_api", AsyncMock()) as api, _quiet() as (email, _):
        await paystack_service.renew_due_plans(db)
        await paystack_service.renew_due_plans(db)
    api.assert_not_awaited()
    assert email.call_count == 1
    context = email.call_args.kwargs["context"]
    assert context["subject"] == "Your lessons renew soon"
    assert "Visa ending 4081" in context["body_text"] and "₦114,000" in context["body_text"]


async def test_admin_can_remove_lessons_added_by_mistake(db):
    from datetime import datetime, timezone

    from app.models.credit_grant import CreditGrant
    from app.services import admin_service, credit_service

    student = await _user(db)
    december = datetime(2027, 12, 31, tzinfo=timezone.utc)
    mistake = await credit_service.grant_credits(db, student_id=student.id, total=1, expires_at=december, source="admin")
    partly = await credit_service.grant_credits(db, student_id=student.id, total=4, expires_at=december, source="admin")
    partly.used = 1
    await db.flush()

    assert await admin_service.remove_unused(db, mistake.id) == {"deleted": True, "removed": 1}
    assert await db.get(CreditGrant, mistake.id) is None
    assert await admin_service.remove_unused(db, partly.id) == {"deleted": False, "removed": 3}
    assert (partly.total, partly.used) == (1, 1)


async def test_two_open_auto_renew_checkouts_make_only_one_renewing_plan(db):
    from app.models.credit_grant import CreditGrant
    from app.models.subscription import Subscription

    student = await _user(db)
    from app.services import paystack_service

    await _auto_plan(db, student, reference="fg_pk_tab1")
    meta = {"kind": "package", "student_id": str(student.id), "product_key": "plan_2x", "auto_renew": True}
    await paystack_service.process_successful_charge(
        db, {"status": "success", "reference": "fg_pk_tab2", "metadata": meta, "authorization": REUSABLE_CARD}
    )
    subs = (await db.execute(select(Subscription).where(Subscription.student_id == student.id))).scalars().all()
    grants = (await db.execute(select(CreditGrant).where(CreditGrant.student_id == student.id))).scalars().all()
    assert len(subs) == 1 and len(grants) == 2  # both months given, one renewal
