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
