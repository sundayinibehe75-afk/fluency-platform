"""Payment service — Stripe checkout, webhook handling, and refunds.

Functions:
- create_checkout_session — create a Stripe Checkout Session for a booking
- handle_webhook — verify and process Stripe webhook events
- initiate_refund — issue a refund via Stripe Refunds API

Prices live in the price_configs table (migration 0003): a single lesson is
1000 cents (USD). Monthly plans are handled in subscription_service; their
webhook events (invoice.paid, customer.subscription.*) are routed from here.
"""
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

import stripe
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.booking import Booking
from app.models.payment import Payment
from app.schemas.payments import CheckoutSessionResponse

# Configure stripe at module level
stripe.api_key = settings.stripe_secret_key

logger = logging.getLogger(__name__)


async def create_checkout_session(
    db: AsyncSession,
    booking_id: uuid.UUID,
    student,
) -> CheckoutSessionResponse:
    """Create a Stripe Checkout Session for the given booking.

    Verifies the booking belongs to the student and is in pending_payment status.
    Creates a Stripe Checkout Session, stores the session ID on the booking,
    and returns the session URL.
    """
    # Fetch the booking
    result = await db.execute(
        select(Booking).where(Booking.id == booking_id)
    )
    booking = result.scalar_one_or_none()

    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Booking not found."},
        )

    # Verify ownership
    if booking.student_id != student.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "FORBIDDEN", "detail": "This booking does not belong to you."},
        )

    # Verify status
    if booking.status != "pending_payment":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "detail": "Booking is not in pending_payment status.",
            },
        )

    # Reservation window expired — the slot may already be released
    now = datetime.now(tz=timezone.utc)
    if booking.reserved_until is not None and booking.reserved_until < now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "RESERVATION_EXPIRED",
                "detail": "Your reservation has expired. Please choose the slot again.",
            },
        )

    if settings.payment_provider == "paystack":
        from app.services import paystack_service

        url = await paystack_service.start_booking_payment(db, booking, student)
        return CheckoutSessionResponse(session_url=url)

    # Create Stripe Checkout Session
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "unit_amount": booking.price_cents,
                    "currency": booking.currency.lower(),
                    "product_data": {
                        "name": "German Lesson",
                    },
                },
                "quantity": 1,
            }
        ],
        success_url=f"{settings.frontend_url}/booking/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.frontend_url}/booking/cancelled",
        metadata={"booking_id": str(booking.id)},
        # Stripe stops accepting payment when our reservation ends (Stripe's
        # minimum is 30 minutes, so the later of the two is used).
        expires_at=int(max(booking.reserved_until or now, now + timedelta(minutes=31)).timestamp()),
    )

    # Store stripe_session_id on booking
    booking.stripe_session_id = session.id
    await db.flush()

    return CheckoutSessionResponse(session_url=session.url)


async def handle_webhook(
    raw_body: bytes,
    stripe_signature: str,
    db: AsyncSession,
) -> dict:
    """Verify and process a Stripe webhook event.

    Verifies the webhook signature using construct_event, then parses the
    raw_body as JSON to get a plain dict (avoids StripeObject access issues).
    """
    # Verify webhook signature (this validates authenticity)
    try:
        stripe.Webhook.construct_event(
            raw_body, stripe_signature, settings.stripe_webhook_secret
        )
    except (stripe.error.SignatureVerificationError, ValueError) as e:
        logger.warning("Stripe webhook signature verification failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "STRIPE_WEBHOOK_INVALID",
                "detail": "Webhook signature verification failed.",
            },
        )

    # Parse raw body as plain JSON dict — no StripeObject quirks
    event = json.loads(raw_body)

    stripe_event_id = event["id"]

    # Idempotency check — skip if already processed
    existing_payment = await db.execute(
        select(Payment).where(Payment.stripe_event_id == stripe_event_id)
    )
    if existing_payment.scalar_one_or_none() is not None:
        logger.info("Duplicate webhook event skipped: %s", stripe_event_id)
        return {"status": "already_processed"}

    event_type = event["type"]

    obj = event["data"]["object"]
    from app.services import subscription_service

    if event_type == "checkout.session.completed" and obj.get("mode") == "subscription":
        await subscription_service.handle_checkout_completed(obj, db)
    elif event_type == "checkout.session.completed":
        await _handle_checkout_completed(event, stripe_event_id, db)
    elif event_type == "invoice.paid":
        await subscription_service.handle_invoice_paid(obj, db)
    elif event_type in ("customer.subscription.updated", "customer.subscription.deleted",
                        "customer.subscription.created"):
        await subscription_service.handle_subscription_changed(obj, db)
    elif event_type == "charge.refund.updated":
        await _handle_refund_updated(event, stripe_event_id, db)
    else:
        logger.info("Unhandled webhook event type: %s", event_type)

    return {"status": "processed"}


async def _handle_checkout_completed(
    event: dict,
    stripe_event_id: str,
    db: AsyncSession,
) -> None:
    """Handle checkout.session.completed event.
    
    Confirms the booking and records the payment inline (without delegating
    to confirm_booking) to avoid MissingGreenlet issues from lazy loads.
    """
    session = event["data"]["object"]  # plain dict from json.loads

    # Extract booking_id from metadata
    booking_id_str = None
    metadata = session.get("metadata") or {}
    if isinstance(metadata, dict):
        booking_id_str = metadata.get("booking_id")
    booking = None

    if booking_id_str:
        booking_id = uuid.UUID(booking_id_str)
        result = await db.execute(
            select(Booking).where(Booking.id == booking_id)
        )
        booking = result.scalar_one_or_none()

    if booking is None:
        # Fallback: find by stripe_session_id
        stripe_session_id = session.get("id")
        result = await db.execute(
            select(Booking).where(Booking.stripe_session_id == stripe_session_id)
        )
        booking = result.scalar_one_or_none()

    if booking is None:
        logger.error(
            "Could not find booking for checkout.session.completed event: %s",
            stripe_event_id,
        )
        return

    # Capture values we need BEFORE any flush (to avoid lazy load issues)
    booking_id_val = booking.id
    booking_price_cents = booking.price_cents
    booking_currency = booking.currency
    booking_slot_id = booking.slot_id

    # Store payment intent ID on booking
    payment_intent_id = session.get("payment_intent")
    if payment_intent_id:
        booking.stripe_payment_intent_id = payment_intent_id

    # Record payment
    payment = Payment(
        booking_id=booking_id_val,
        stripe_event_id=stripe_event_id,
        event_type="checkout.session.completed",
        amount_cents=booking_price_cents,
        currency=booking_currency,
        status="succeeded",
    )
    db.add(payment)

    from app.models.availability_slot import AvailabilitySlot

    # If the reservation expired before payment arrived, the slot may already
    # belong to someone else. In that case refund instead of double-booking.
    if booking.status == "cancelled":
        from app.services import slot_service

        old_slot = (
            await db.execute(select(AvailabilitySlot).where(AvailabilitySlot.id == booking_slot_id))
        ).scalar_one_or_none()
        usable = await slot_service.reclaim(db, old_slot) if old_slot is not None else None
        if usable is not None:
            booking.slot_id = booking_slot_id = usable.id
        else:
            await db.flush()
            logger.warning(
                "Payment arrived for an expired booking whose slot was taken — refunding",
                extra={"booking_id": str(booking_id_val)},
            )
            try:
                await initiate_refund(db, booking_id_val)
            except Exception:
                logger.exception(
                    "Automatic refund failed — needs manual follow-up",
                    extra={"booking_id": str(booking_id_val)},
                )
            return

    # Confirm the booking inline (set status, mark slot as booked)
    booking.status = "confirmed"
    booking.reserved_until = None

    slot_result = await db.execute(
        select(AvailabilitySlot).where(AvailabilitySlot.id == booking_slot_id)
    )
    slot = slot_result.scalar_one_or_none()
    if slot is not None:
        slot.status = "booked"

    # Flush all changes — after this, don't access ORM objects
    await db.flush()

    # Confirmation email + video room (never raises)
    from app.services.booking_service import notify_booking_confirmed

    await notify_booking_confirmed(db, booking_id_val)

    logger.info(
        "Booking confirmed via webhook",
        extra={
            "booking_id": str(booking_id_val),
            "stripe_event_id": stripe_event_id,
        },
    )


async def _handle_refund_updated(
    event: dict,
    stripe_event_id: str,
    db: AsyncSession,
) -> None:
    """Handle charge.refund.updated event — record refund and update booking status."""
    refund_obj = event["data"]["object"]  # plain dict from json.loads
    if refund_obj.get("status") not in (None, "succeeded"):
        # pending/failed updates: only a finished refund is recorded, so the
        # same refund is never counted twice
        return
    payment_intent_id = refund_obj.get("payment_intent")
    amount_refunded = refund_obj.get("amount", 0)
    currency = refund_obj.get("currency", "usd").upper()

    # Find booking by stripe_payment_intent_id
    booking = None
    if payment_intent_id:
        result = await db.execute(
            select(Booking).where(
                Booking.stripe_payment_intent_id == payment_intent_id
            )
        )
        booking = result.scalar_one_or_none()

    if booking is None:
        logger.error(
            "Could not find booking for charge.refund.updated event: %s",
            stripe_event_id,
        )
        return

    # Record refund in payments table
    payment = Payment(
        booking_id=booking.id,
        stripe_event_id=stripe_event_id,
        event_type="charge.refund.updated",
        amount_cents=amount_refunded,
        currency=currency,
        status="refunded",
    )
    db.add(payment)

    # Update booking status to refunded
    booking.status = "refunded"

    logger.info(
        "Refund recorded via webhook",
        extra={
            "booking_id": str(booking.id),
            "stripe_event_id": stripe_event_id,
            "amount_cents": amount_refunded,
        },
    )


async def initiate_refund(
    db: AsyncSession,
    booking_id: uuid.UUID,
) -> bool:
    """Initiate a refund for a booking via Stripe Refunds API.

    Fetches the booking and calls stripe.Refund.create with the
    payment intent ID.
    """
    result = await db.execute(
        select(Booking).where(Booking.id == booking_id)
    )
    booking = result.scalar_one_or_none()

    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Booking not found."},
        )

    if booking.payment_provider == "paystack" and booking.payment_reference:
        from app.services import paystack_service

        await paystack_service.refund(booking.payment_reference)
        return True

    if not booking.stripe_payment_intent_id:
        logger.warning(
            "Cannot refund booking without payment intent ID: %s",
            str(booking_id),
        )
        return False

    stripe.Refund.create(payment_intent=booking.stripe_payment_intent_id)

    logger.info(
        "Refund initiated",
        extra={
            "booking_id": str(booking_id),
            "payment_intent_id": booking.stripe_payment_intent_id,
        },
    )
    return True
