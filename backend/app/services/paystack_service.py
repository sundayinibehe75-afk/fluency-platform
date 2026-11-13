"""Paystack payments: single lessons and prepaid monthly lesson packages.

How it works:
- Prices stay in US dollars (price_configs). At checkout the dollar price is
  converted to naira at the live market rate (plus any admin markup),
  because a Nigerian Paystack account charges in NGN. The student's bank
  converts it to their own currency.
- We start a transaction on Paystack and send the student to its payment page
  (authorization_url). Paystack then sends them back to our site with the
  transaction reference.
- A payment counts only after we confirm it with Paystack: through the
  charge.success webhook (signed with our secret key) or by asking the verify
  API when the student returns. Both paths run the same idempotent code, so
  whichever comes first does the work and the other changes nothing.
- A package gives a month of lessons, valid for PACKAGE_DAYS days. The
  student chooses whether it renews: with "Renew automatically" ticked we keep
  Paystack's reusable authorization for their card (never the card number) in
  a Subscription row, and renew_due_plans() charges it when the month ends.
  Students get an email RENEWAL_REMINDER_DAYS before each renewal, can turn
  renewal off at any time, and a card that fails MAX_RENEWAL_FAILURES times in
  a row (one try a day) stops the renewal.
"""
import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.app_setting import AppSetting
from app.models.availability_slot import AvailabilitySlot
from app.models.booking import Booking
from app.models.credit_grant import CreditGrant
from app.models.payment import Payment
from app.models.price_config import PriceConfig
from app.models.subscription import Subscription
from app.models.user import User

logger = logging.getLogger(__name__)

API_BASE = "https://api.paystack.co"
RATE_KEY = "ngn_per_usd"
PACKAGE_DAYS = 30
RENEWAL_REMINDER_DAYS = 3
MAX_RENEWAL_FAILURES = 3
RETRY_AFTER = timedelta(hours=23)
CURRENCY = "NGN"


# ---------------------------------------------------------------------------
# Exchange rate
#
# The naira rate comes from a live market feed (open.er-api.com, free, no key,
# updated daily) and is cached in app_settings for LIVE_TTL. The admin can add
# a markup % on top (e.g. to cover card fees). The admin's own saved rate is a
# backup, used only when the feed has been unreachable for longer than
# LIVE_MAX_AGE.
# ---------------------------------------------------------------------------

LIVE_URL = "https://open.er-api.com/v6/latest/USD"
LIVE_KEY = "ngn_per_usd_live"
LIVE_AT_KEY = "ngn_per_usd_live_at"
MARKUP_KEY = "rate_markup_pct"
LIVE_TTL = timedelta(hours=6)
LIVE_MAX_AGE = timedelta(days=3)
MIN_RATE, MAX_RATE = Decimal("100"), Decimal("100000")


async def _get_setting(db: AsyncSession, key: str) -> str | None:
    row = (await db.execute(select(AppSetting).where(AppSetting.key == key))).scalar_one_or_none()
    return row.value if row else None


async def _put_setting(db: AsyncSession, key: str, value: str) -> None:
    row = (await db.execute(select(AppSetting).where(AppSetting.key == key))).scalar_one_or_none()
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    await db.flush()


def _decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


async def _fetch_live_rate() -> Decimal | None:
    """Today's market naira rate for one US dollar, or None if unavailable."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(LIVE_URL)
        data = resp.json()
        if resp.status_code != 200 or data.get("result") != "success":
            logger.warning("Live rate feed returned %s", resp.status_code)
            return None
        rate = Decimal(str(data["rates"]["NGN"]))
    except (httpx.HTTPError, ValueError, KeyError, TypeError, InvalidOperation) as exc:
        logger.warning("Live rate feed failed: %s", exc)
        return None
    return rate if MIN_RATE <= rate <= MAX_RATE else None


async def get_rate_info(db: AsyncSession) -> dict:
    """The rate used at checkout and where it came from.

    rate        — naira per dollar charged (live x markup, or the backup rate)
    source      — "live", "backup" or None (no usable rate)
    """
    now = datetime.now(timezone.utc)
    live = _decimal(await _get_setting(db, LIVE_KEY))
    live_at_raw = await _get_setting(db, LIVE_AT_KEY)
    live_at = datetime.fromisoformat(live_at_raw) if live_at_raw else None

    if live is None or live_at is None or now - live_at > LIVE_TTL:
        fresh = await _fetch_live_rate()
        if fresh is not None:
            live, live_at = fresh, now
            await _put_setting(db, LIVE_KEY, str(fresh))
            await _put_setting(db, LIVE_AT_KEY, now.isoformat())

    markup = _decimal(await _get_setting(db, MARKUP_KEY)) or Decimal("0")
    backup = _decimal(await _get_setting(db, RATE_KEY))
    if backup is not None and backup <= 0:
        backup = None

    if live is not None and live_at is not None and now - live_at <= LIVE_MAX_AGE:
        rate = (live * (1 + markup / 100)).quantize(Decimal("0.01"))
        source = "live"
    elif backup is not None:
        rate, source = backup, "backup"
    else:
        rate, source = None, None

    return {
        "rate": rate,
        "source": source,
        "live_rate": live,
        "live_updated_at": live_at,
        "markup_pct": markup,
        "backup_rate": backup,
    }


async def get_rate(db: AsyncSession) -> Decimal | None:
    return (await get_rate_info(db))["rate"]


async def set_rate(db: AsyncSession, rate: Decimal) -> Decimal:
    """Save the admin's backup rate (used only when the live feed is down)."""
    if rate < MIN_RATE or rate > MAX_RATE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "detail": "Enter a realistic naira rate, e.g. 1500."},
        )
    await _put_setting(db, RATE_KEY, str(rate))
    return rate


async def set_markup(db: AsyncSession, pct: Decimal) -> Decimal:
    if pct < 0 or pct > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "detail": "Markup must be between 0 and 20%."},
        )
    await _put_setting(db, MARKUP_KEY, str(pct))
    return pct


async def _require_rate(db: AsyncSession) -> Decimal:
    rate = await get_rate(db)
    if rate is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "PAYMENTS_NOT_READY", "detail": "Payments are not set up yet. Please try again later."},
        )
    return rate


def usd_cents_to_kobo(usd_cents: int, rate: Decimal) -> int:
    """$10.00 (1000 cents) at ₦1500/$ = ₦15,000 = 1,500,000 kobo."""
    return int((Decimal(usd_cents) * rate).to_integral_value())


# ---------------------------------------------------------------------------
# Paystack API
# ---------------------------------------------------------------------------


def _headers() -> dict:
    if not settings.paystack_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "PAYMENTS_NOT_READY", "detail": "Payments are not set up yet. Please try again later."},
        )
    return {"Authorization": f"Bearer {settings.paystack_secret_key}"}


async def _api(method: str, path: str, json: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.request(method, f"{API_BASE}{path}", headers=_headers(), json=json)
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code >= 400 or not body.get("status"):
        logger.error(
            "Paystack API error",
            extra={"path": path, "status_code": response.status_code, "message": body.get("message")},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "PAYMENT_PROVIDER_ERROR", "detail": "The payment service is not available. Please try again."},
        )
    return body.get("data") or {}


def _new_reference(kind: str) -> str:
    return f"fg_{kind}_{uuid.uuid4().hex[:16]}_{secrets.token_hex(3)}"


def verify_signature(raw_body: bytes, signature: str | None) -> bool:
    """Paystack signs webhooks with HMAC-SHA512 of the body using the secret key."""
    if not signature or not settings.paystack_secret_key:
        return False
    expected = hmac.new(settings.paystack_secret_key.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Starting payments
# ---------------------------------------------------------------------------


async def start_booking_payment(db: AsyncSession, booking: Booking, student: User) -> str:
    """Start paying for a single lesson; returns the Paystack payment page URL."""
    rate = await _require_rate(db)
    reference = _new_reference("bk")
    data = await _api(
        "POST",
        "/transaction/initialize",
        {
            "email": student.email,
            "amount": usd_cents_to_kobo(booking.price_cents, rate),
            "currency": CURRENCY,
            "reference": reference,
            "callback_url": f"{settings.frontend_url}/booking/success",
            "metadata": {
                "kind": "booking",
                "booking_id": str(booking.id),
                "usd_cents": booking.price_cents,
                "cancel_action": f"{settings.frontend_url}/booking/cancelled",
            },
        },
    )
    booking.payment_provider = "paystack"
    booking.payment_reference = reference
    await db.flush()
    return data["authorization_url"]


async def start_package_payment(
    db: AsyncSession, student: User, plan: PriceConfig, auto_renew: bool = False
) -> str:
    """Start paying for a monthly lesson package; returns the payment page URL.

    auto_renew: the student ticked "Renew automatically", so the card is saved
    for next month when this payment succeeds.
    """
    if auto_renew and await live_auto_plan(db, student.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "PLAN_EXISTS",
                "detail": "You already have a plan that renews automatically. "
                          "Turn off its renewal first, or buy this month without renewal.",
            },
        )
    rate = await _require_rate(db)
    reference = _new_reference("pk")
    data = await _api(
        "POST",
        "/transaction/initialize",
        {
            "email": student.email,
            "amount": usd_cents_to_kobo(plan.price_cents, rate),
            "currency": CURRENCY,
            "reference": reference,
            "callback_url": f"{settings.frontend_url}/dashboard",
            "metadata": {
                "kind": "package",
                "student_id": str(student.id),
                "product_key": plan.product_key,
                "usd_cents": plan.price_cents,
                "auto_renew": bool(auto_renew),
                "cancel_action": f"{settings.frontend_url}/#pricing",
            },
        },
    )
    return data["authorization_url"]


async def live_auto_plan(db: AsyncSession, student_id: uuid.UUID) -> Subscription | None:
    """The student's Paystack plan that is still renewing, if any."""
    return (
        await db.execute(
            select(Subscription)
            .where(
                Subscription.student_id == student_id,
                Subscription.provider == "paystack",
                Subscription.status.in_(["active", "past_due"]),
                Subscription.cancel_at_period_end.is_(False),
            )
            .limit(1)
        )
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Confirming payments (webhook and verify share this)
# ---------------------------------------------------------------------------


async def process_successful_charge(db: AsyncSession, data: dict) -> str:
    """Apply a successful Paystack transaction. Safe to call more than once.

    Returns what happened: "booking_confirmed", "package_granted",
    "already_processed", "ignored".
    """
    if data.get("status") != "success":
        return "ignored"
    reference = data.get("reference")
    metadata = data.get("metadata") or {}
    if not reference or not isinstance(metadata, dict):
        return "ignored"

    kind = metadata.get("kind")
    if kind == "booking":
        return await _confirm_booking(db, reference, metadata.get("booking_id"))
    if kind == "package":
        return await _grant_package(db, reference, metadata, data)
    return "ignored"


async def _confirm_booking(db: AsyncSession, reference: str, booking_id: str | None = None) -> str:
    event_id = f"paystack:{reference}"
    if (await db.execute(select(Payment.id).where(Payment.stripe_event_id == event_id))).first():
        return "already_processed"

    booking = (
        await db.execute(select(Booking).where(Booking.payment_reference == reference).with_for_update())
    ).scalar_one_or_none()
    if booking is None and booking_id:
        # A student can leave the payment page and start a new payment for the
        # same booking, which replaces the stored reference. If the earlier
        # attempt is the one that was paid, find the booking from the metadata.
        try:
            booking = (
                await db.execute(select(Booking).where(Booking.id == uuid.UUID(booking_id)).with_for_update())
            ).scalar_one_or_none()
        except ValueError:
            booking = None
        if booking is not None:
            if booking.status == "confirmed":
                # Already paid through the other attempt: refund this one.
                db.add(
                    Payment(
                        booking_id=booking.id,
                        stripe_event_id=event_id,
                        event_type="paystack.charge.duplicate",
                        amount_cents=booking.price_cents,
                        currency=booking.currency,
                        status="duplicate",  # refunded, not counted as income
                    )
                )
                await db.flush()
                logger.warning("Duplicate Paystack payment for a booking — refunding", extra={"reference": reference})
                try:
                    await refund(reference)
                except Exception:
                    logger.exception("Automatic refund failed — needs manual follow-up", extra={"reference": reference})
                return "already_processed"
            booking.payment_reference = reference
    if booking is None:
        logger.error("Paystack payment for unknown booking", extra={"reference": reference})
        return "ignored"

    db.add(
        Payment(
            booking_id=booking.id,
            stripe_event_id=event_id,
            event_type="paystack.charge.success",
            amount_cents=booking.price_cents,
            currency=booking.currency,
            status="succeeded",
        )
    )

    # Paid after the 15-minute hold ran out and someone else took the slot:
    # refund instead of double-booking.
    if booking.status == "cancelled":
        taken = (
            await db.execute(
                select(Booking.id).where(
                    Booking.slot_id == booking.slot_id,
                    Booking.id != booking.id,
                    Booking.status.in_(["pending_payment", "confirmed"]),
                )
            )
        ).first()
        if taken is not None:
            await db.flush()
            logger.warning("Paystack payment arrived for a taken slot — refunding", extra={"reference": reference})
            try:
                await refund(reference)
            except Exception:
                logger.exception("Automatic refund failed — needs manual follow-up", extra={"reference": reference})
            return "booking_confirmed"

    booking.status = "confirmed"
    booking.reserved_until = None
    slot = (
        await db.execute(select(AvailabilitySlot).where(AvailabilitySlot.id == booking.slot_id))
    ).scalar_one_or_none()
    if slot is not None:
        slot.status = "booked"
    await db.flush()

    from app.services.booking_service import notify_booking_confirmed

    await notify_booking_confirmed(db, booking.id)
    logger.info("Booking paid with Paystack", extra={"booking_id": str(booking.id)})
    return "booking_confirmed"


def _card_label(authorization: dict) -> str | None:
    brand = (authorization.get("brand") or authorization.get("card_type") or "Card").strip().title()
    last4 = authorization.get("last4")
    return f"{brand} ending {last4}"[:60] if last4 else None


async def _grant_package(db: AsyncSession, reference: str, metadata: dict, data: dict | None = None) -> str:
    if (await db.execute(select(CreditGrant.id).where(CreditGrant.payment_reference == reference))).first():
        return "already_processed"

    plan = (
        await db.execute(select(PriceConfig).where(PriceConfig.product_key == metadata.get("product_key")))
    ).scalar_one_or_none()
    try:
        student_id = uuid.UUID(str(metadata.get("student_id")))
    except ValueError:
        student_id = None
    if plan is None or not plan.lessons_per_month or student_id is None:
        logger.error("Paystack package payment with bad metadata", extra={"reference": reference})
        return "ignored"

    now = datetime.now(tz=timezone.utc)
    renewing = None
    if metadata.get("subscription_id"):
        try:
            renewing = (
                await db.execute(
                    select(Subscription).where(Subscription.id == uuid.UUID(str(metadata["subscription_id"])))
                )
            ).scalar_one_or_none()
        except ValueError:
            renewing = None

    # A renewal continues from the end of the previous month (no gap, no
    # overlap), unless that was more than a day ago.
    starts = now
    if renewing is not None and renewing.current_period_end and renewing.current_period_end > now - timedelta(days=1):
        starts = renewing.current_period_end

    grant = CreditGrant(
        student_id=student_id,
        source="package",
        total=plan.lessons_per_month,
        used=0,
        expires_at=starts + timedelta(days=PACKAGE_DAYS),
        payment_reference=reference,
        amount_cents=plan.price_cents,
        note=plan.label,
    )
    db.add(grant)

    if renewing is not None:
        renewing.status = "active"
        renewing.current_period_end = grant.expires_at
        renewing.renewal_failures = 0
        renewing.last_charge_attempt_at = None
    elif metadata.get("auto_renew") in (True, "true", "True", 1):
        authorization = (data or {}).get("authorization") or {}
        if authorization.get("reusable") and authorization.get("authorization_code"):
            db.add(
                Subscription(
                    student_id=student_id,
                    product_key=plan.product_key,
                    stripe_subscription_id=f"paystack:{uuid.uuid4()}",
                    provider="paystack",
                    status="active",
                    cancel_at_period_end=False,
                    current_period_end=grant.expires_at,
                    paystack_authorization_code=authorization["authorization_code"],
                    card_label=_card_label(authorization),
                )
            )
        else:
            logger.warning(
                "Card can't be charged again; package will not renew", extra={"reference": reference}
            )

    await db.flush()
    logger.info(
        "Lesson package granted",
        extra={"student_id": str(student_id), "product_key": plan.product_key, "lessons": plan.lessons_per_month},
    )
    return "package_granted"


async def verify_and_process(db: AsyncSession, reference: str, user: User) -> dict:
    """Called when the student comes back from Paystack with ?reference=..."""
    data = await _api("GET", f"/transaction/verify/{reference}")
    metadata = data.get("metadata") or {}
    # Only the person who paid (or the admin) may look at the result
    if user.role != "admin":
        owner = metadata.get("student_id")
        if metadata.get("kind") == "booking":
            booking = (
                await db.execute(select(Booking).where(Booking.payment_reference == reference))
            ).scalar_one_or_none()
            owner = str(booking.student_id) if booking else None
        if owner != str(user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "detail": "This payment does not belong to you."},
            )
    result = await process_successful_charge(db, data)
    return {"status": data.get("status"), "kind": metadata.get("kind"), "result": result}


# ---------------------------------------------------------------------------
# Webhook and refunds
# ---------------------------------------------------------------------------


async def handle_webhook(db: AsyncSession, raw_body: bytes, signature: str | None) -> dict:
    if not verify_signature(raw_body, signature):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "WEBHOOK_INVALID", "detail": "Signature check failed."},
        )
    import json

    event = json.loads(raw_body)
    name = event.get("event")
    data = event.get("data") or {}
    if name == "charge.success":
        return {"status": await process_successful_charge(db, data)}
    if name == "refund.processed":
        return {"status": await _record_refund(db, data)}
    logger.info("Unhandled Paystack event", extra={"event": name})
    return {"status": "ignored"}


async def refund(reference: str) -> None:
    """Ask Paystack to refund the whole transaction."""
    await _api("POST", "/refund", {"transaction": reference})
    logger.info("Paystack refund requested", extra={"reference": reference})


async def _record_refund(db: AsyncSession, data: dict) -> str:
    reference = data.get("transaction_reference") or (data.get("transaction") or {}).get("reference")
    if not reference:
        return "ignored"
    event_id = f"paystack-refund:{reference}"
    if (await db.execute(select(Payment.id).where(Payment.stripe_event_id == event_id))).first():
        return "already_processed"
    booking = (
        await db.execute(select(Booking).where(Booking.payment_reference == reference))
    ).scalar_one_or_none()
    if booking is None:
        return "ignored"
    db.add(
        Payment(
            booking_id=booking.id,
            stripe_event_id=event_id,
            event_type="paystack.refund.processed",
            amount_cents=booking.price_cents,
            currency=booking.currency,
            status="refunded",
        )
    )
    booking.status = "refunded"
    await db.flush()
    return "refund_recorded"


# ---------------------------------------------------------------------------
# Automatic renewal (background job, hourly)
# ---------------------------------------------------------------------------


def _plan_email(student: User, subject: str, heading: str, body: str, button: str, url: str) -> None:
    import html

    from app.services.notification_service import send_email_later

    send_email_later(
        to=student.email,
        template_name="plan_notice",
        context={
            "subject": subject,
            "heading": heading,
            "first_name": html.escape(student.first_name or "there"),
            "body_text": body,
            "button_label": button,
            "button_url": url,
        },
    )


def _naira(kobo: int) -> str:
    return f"₦{kobo / 100:,.0f}"


async def renew_due_plans(db: AsyncSession) -> int:
    """Remind, renew, retry or stop Paystack plans. Returns plans renewed."""
    from app.core import timefmt

    now = datetime.now(tz=timezone.utc)
    subs = (
        await db.execute(
            select(Subscription).where(
                Subscription.provider == "paystack",
                Subscription.status.in_(["active", "past_due"]),
            )
        )
    ).scalars().all()

    renewed = 0
    for sub in subs:
        end = sub.current_period_end
        if end is None:
            continue
        if sub.cancel_at_period_end:
            if end <= now:
                sub.status = "canceled"
            continue

        student = await db.get(User, sub.student_id)
        plan = (
            await db.execute(select(PriceConfig).where(PriceConfig.product_key == sub.product_key))
        ).scalar_one_or_none()
        if student is None or plan is None or not sub.paystack_authorization_code:
            sub.status = "canceled"
            continue
        dashboard = f"{settings.frontend_url}/dashboard"

        # Heads-up a few days before the card is charged
        if now < end <= now + timedelta(days=RENEWAL_REMINDER_DAYS) and sub.reminder_sent_for != end:
            rate = await get_rate(db)
            amount = f" for about {_naira(usd_cents_to_kobo(plan.price_cents, rate))}" if rate else ""
            _plan_email(
                student,
                "Your lessons renew soon",
                "Your plan renews soon",
                f"Your {plan.label} plan renews automatically on "
                f"<strong>{timefmt.lesson_date(end, student.timezone)}</strong>{amount}"
                f" (${plan.price_cents / 100:,.2f}), charged to your {sub.card_label or 'saved card'}. "
                "Don't want to continue? Turn off renewal in your dashboard before then.",
                "Manage my plan",
                dashboard,
            )
            sub.reminder_sent_for = end
            continue

        if end > now:
            continue
        if sub.last_charge_attempt_at and now - sub.last_charge_attempt_at < RETRY_AFTER:
            continue

        rate = await get_rate(db)
        if rate is None:
            logger.error("No exchange rate: plan renewal postponed", extra={"subscription_id": str(sub.id)})
            continue

        sub.last_charge_attempt_at = now
        reference = _new_reference("rn")
        metadata = {
            "kind": "package",
            "student_id": str(sub.student_id),
            "product_key": plan.product_key,
            "usd_cents": plan.price_cents,
            "subscription_id": str(sub.id),
        }
        try:
            data = await _api(
                "POST",
                "/transaction/charge_authorization",
                {
                    "email": student.email,
                    "amount": usd_cents_to_kobo(plan.price_cents, rate),
                    "currency": CURRENCY,
                    "authorization_code": sub.paystack_authorization_code,
                    "reference": reference,
                    "metadata": metadata,
                },
            )
            outcome = data.get("status")
        except HTTPException:
            outcome = "failed"

        if outcome == "success":
            await _grant_package(db, reference, metadata, data)
            renewed += 1
            _plan_email(
                student,
                "Your plan has renewed",
                "Your new month of lessons is ready",
                f"We charged your {sub.card_label or 'saved card'} for your {plan.label} plan. "
                f"You have {plan.lessons_per_month} new lessons to book.",
                "Book lessons",
                f"{settings.frontend_url}/booking?type=plan",
            )
            continue
        if outcome not in ("failed", "reversed", "abandoned"):
            # Still processing (e.g. "pending"): the charge.success webhook
            # finishes it; if it never arrives we try again tomorrow.
            continue

        sub.renewal_failures += 1
        if sub.renewal_failures >= MAX_RENEWAL_FAILURES:
            sub.status = "canceled"
            _plan_email(
                student,
                "Your plan has stopped",
                "We couldn't renew your plan",
                f"Payment for your {plan.label} plan failed {MAX_RENEWAL_FAILURES} times, so automatic "
                "renewal has stopped and your card won't be charged again. "
                "You can buy a new month any time on the Pricing page.",
                "See plans",
                f"{settings.frontend_url}/#pricing",
            )
        else:
            sub.status = "past_due"
            _plan_email(
                student,
                "Your plan renewal payment failed",
                "Your renewal payment didn't go through",
                f"We couldn't charge your {sub.card_label or 'saved card'} for your {plan.label} plan. "
                "We'll try again tomorrow. Please make sure the card has enough funds, "
                "or turn off renewal and buy a month with another card.",
                "Manage my plan",
                dashboard,
            )
    await db.flush()
    return renewed
