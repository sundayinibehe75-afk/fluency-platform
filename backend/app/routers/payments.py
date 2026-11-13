"""Payments router — Stripe checkout and webhook endpoints.

Endpoints:
- POST /payments/checkout — create a Stripe Checkout Session (student auth)
- POST /payments/webhook — handle Stripe webhook events (no auth, raw body)
- GET  /payments/config — public: provider and naira rate for showing prices
- POST /payments/paystack/webhook — Paystack events (signed, no auth)
- GET  /payments/paystack/verify?reference= — confirm a payment on return
"""
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.models.user import User
from pydantic import BaseModel

from app.schemas.payments import CheckoutSessionResponse
from app.core.config import settings
from app.services import payment_service, paystack_service

router = APIRouter(prefix="/payments", tags=["payments"])


class CheckoutRequest(BaseModel):
    """Request body for creating a checkout session."""

    booking_id: uuid.UUID


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout(
    body: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    student: User = Depends(require_role("student")),
) -> CheckoutSessionResponse:
    """Create a Stripe Checkout Session for a booking.

    Requires student authentication. The booking must belong to the
    authenticated student and be in pending_payment status.
    """
    return await payment_service.create_checkout_session(
        db=db,
        booking_id=body.booking_id,
        student=student,
    )


@router.get("/config")
async def payment_config(db: AsyncSession = Depends(get_db)) -> dict:
    """What the frontend needs to show prices: provider and naira rate."""
    rate = await paystack_service.get_rate(db) if settings.payment_provider == "paystack" else None
    return {
        "provider": settings.payment_provider,
        "charge_currency": "NGN" if settings.payment_provider == "paystack" else "USD",
        "ngn_per_usd": float(rate) if rate is not None else None,
        "auto_renew": settings.payment_provider == "stripe",
    }


@router.post("/paystack/webhook")
async def paystack_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_paystack_signature: str | None = Header(default=None, alias="x-paystack-signature"),
) -> dict:
    """Paystack events. Verified with the HMAC-SHA512 signature header."""
    raw_body = await request.body()
    return await paystack_service.handle_webhook(db, raw_body, x_paystack_signature)


@router.get("/paystack/verify")
async def paystack_verify(
    reference: str = Query(..., min_length=5, max_length=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
) -> dict:
    """The student is back from Paystack: confirm the payment straight away."""
    return await paystack_service.verify_and_process(db, reference, user)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str = Header(alias="stripe-signature"),
) -> dict:
    """Handle Stripe webhook events.

    No authentication — uses raw body and Stripe signature header
    for verification. Must use Request.body() to get raw bytes for
    signature verification.
    """
    raw_body = await request.body()
    return await payment_service.handle_webhook(
        raw_body=raw_body,
        stripe_signature=stripe_signature,
        db=db,
    )
