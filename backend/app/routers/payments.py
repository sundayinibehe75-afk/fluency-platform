"""Payments router — Stripe checkout and webhook endpoints.

Endpoints:
- POST /payments/checkout — create a Stripe Checkout Session (student auth)
- POST /payments/webhook — handle Stripe webhook events (no auth, raw body)
"""
import uuid

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.models.user import User
from pydantic import BaseModel

from app.schemas.payments import CheckoutSessionResponse
from app.services import payment_service

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
