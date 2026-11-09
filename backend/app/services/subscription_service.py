"""Monthly plans — Stripe subscriptions that renew automatically.

How it works:
- The student picks a plan (2x, 3x, 4x or 5x a week) and pays through Stripe
  Checkout in subscription mode. Stripe then bills them every month until
  they cancel.
- Every paid invoice (invoice.paid webhook) gives the student that month's
  lesson credits. The credits expire at the end of the billing month, so
  unused lessons do not roll over.
- Cancelling stops the renewal. The student keeps the current month and its
  credits until the period ends.
"""
import logging
import uuid
from datetime import datetime, timezone

import stripe
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.credit_grant import CreditGrant
from app.models.price_config import PriceConfig
from app.models.subscription import Subscription
from app.models.user import User
from app.services import credit_service

logger = logging.getLogger(__name__)

# Stripe statuses where the plan is still running
LIVE_STATUSES = ("active", "trialing", "past_due", "incomplete")


def _ts(value) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc)


def _get(obj, key, default=None):
    """Read a key from a dict or a StripeObject."""
    if obj is None:
        return default
    try:
        value = obj[key]
    except (KeyError, TypeError, AttributeError):
        value = getattr(obj, key, default)
    return default if value is None else value


def _period_end_of(sub_obj) -> datetime | None:
    """current_period_end moved onto the subscription items in newer Stripe APIs."""
    end = _get(sub_obj, "current_period_end")
    if not end:
        items = _get(_get(sub_obj, "items", {}), "data", []) or []
        if items:
            end = _get(items[0], "current_period_end")
    return _ts(end)


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


async def list_prices(db: AsyncSession) -> list[dict]:
    """Active prices for the pricing page: the single lesson and the plans."""
    result = await db.execute(
        select(PriceConfig)
        .where(PriceConfig.is_active.is_(True))
        .order_by(PriceConfig.sort_order, PriceConfig.price_cents)
    )
    return [
        {
            "product_key": p.product_key,
            "label": p.label,
            "price_cents": p.price_cents,
            "currency": p.currency,
            "lessons_per_month": p.lessons_per_month,
            "is_plan": p.lessons_per_month is not None,
        }
        for p in result.scalars()
    ]


async def _get_plan(db: AsyncSession, product_key: str) -> PriceConfig:
    result = await db.execute(
        select(PriceConfig).where(
            PriceConfig.product_key == product_key,
            PriceConfig.is_active.is_(True),
            PriceConfig.lessons_per_month.is_not(None),
        )
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Plan not found."},
        )
    return plan


async def get_live_subscription(db: AsyncSession, student_id: uuid.UUID) -> Subscription | None:
    result = await db.execute(
        select(Subscription)
        .where(
            Subscription.student_id == student_id,
            Subscription.status.in_(LIVE_STATUSES),
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Student actions
# ---------------------------------------------------------------------------


async def create_checkout(db: AsyncSession, student: User, product_key: str) -> dict:
    """Start Stripe Checkout for a monthly plan."""
    plan = await _get_plan(db, product_key)

    if await get_live_subscription(db, student.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "PLAN_EXISTS",
                "detail": "You already have a plan. Cancel it first to choose a different one.",
            },
        )

    # Reuse the Stripe customer from an earlier plan, if there is one
    previous = await db.execute(
        select(Subscription.stripe_customer_id)
        .where(Subscription.student_id == student.id, Subscription.stripe_customer_id.is_not(None))
        .limit(1)
    )
    customer_id = previous.scalar_one_or_none()

    metadata = {"student_id": str(student.id), "product_key": plan.product_key}
    params = dict(
        mode="subscription",
        line_items=[
            {
                "price_data": {
                    "currency": plan.currency.lower(),
                    "unit_amount": plan.price_cents,
                    "recurring": {"interval": "month"},
                    "product_data": {"name": f"German lessons: {plan.label}"},
                },
                "quantity": 1,
            }
        ],
        success_url=f"{settings.frontend_url}/dashboard?plan=success",
        cancel_url=f"{settings.frontend_url}/pricing",
        metadata=metadata,
        subscription_data={"metadata": metadata},
    )
    if customer_id:
        params["customer"] = customer_id
    else:
        params["customer_email"] = student.email

    session = stripe.checkout.Session.create(**params)
    return {"session_url": session.url}


async def cancel_subscription(db: AsyncSession, student: User) -> dict:
    """Stop renewal. The student keeps the current month."""
    sub = await get_live_subscription(db, student.id)
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "You don't have an active plan."},
        )
    if not sub.cancel_at_period_end:
        stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=True)
        sub.cancel_at_period_end = True
        await db.flush()
    logger.info("Plan cancelled at period end", extra={"student_id": str(student.id)})
    return await my_plan(db, student.id)


async def resume_subscription(db: AsyncSession, student: User) -> dict:
    """Undo a cancellation before the month ends."""
    sub = await get_live_subscription(db, student.id)
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "You don't have an active plan."},
        )
    if sub.cancel_at_period_end:
        stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=False)
        sub.cancel_at_period_end = False
        await db.flush()
    return await my_plan(db, student.id)


async def my_plan(db: AsyncSession, student_id: uuid.UUID) -> dict:
    """Plan, credits and free-trial status for the student dashboard."""
    sub = await get_live_subscription(db, student_id)
    plan_info = None
    if sub is not None:
        price = (
            await db.execute(select(PriceConfig).where(PriceConfig.product_key == sub.product_key))
        ).scalar_one_or_none()
        plan_info = {
            "product_key": sub.product_key,
            "label": price.label if price else sub.product_key,
            "price_cents": price.price_cents if price else None,
            "lessons_per_month": price.lessons_per_month if price else None,
            "status": sub.status,
            "cancel_at_period_end": sub.cancel_at_period_end,
            "current_period_end": sub.current_period_end,
        }
    summary = await credit_service.credit_summary(db, student_id)
    return {
        "plan": plan_info,
        **summary,
        "trial_available": await credit_service.trial_available(db, student_id),
    }


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------


async def _upsert_subscription(db: AsyncSession, sub_obj) -> Subscription | None:
    """Create or update our record from a Stripe subscription object."""
    stripe_id = _get(sub_obj, "id")
    if not stripe_id:
        return None
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_id)
    )
    sub = result.scalar_one_or_none()
    metadata = _get(sub_obj, "metadata", {}) or {}

    if sub is None:
        student_id = _get(metadata, "student_id")
        product_key = _get(metadata, "product_key")
        if not student_id or not product_key:
            logger.error("Stripe subscription without student metadata: %s", stripe_id)
            return None
        sub = Subscription(
            student_id=uuid.UUID(student_id),
            product_key=product_key,
            stripe_subscription_id=stripe_id,
            status=_get(sub_obj, "status", "incomplete"),
        )
        db.add(sub)

    sub.status = _get(sub_obj, "status", sub.status)
    sub.cancel_at_period_end = bool(_get(sub_obj, "cancel_at_period_end", False))
    sub.current_period_end = _period_end_of(sub_obj) or sub.current_period_end
    customer = _get(sub_obj, "customer")
    if isinstance(customer, str):
        sub.stripe_customer_id = customer
    await db.flush()
    return sub


async def _load_subscription(db: AsyncSession, stripe_id: str) -> Subscription | None:
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_id)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        # invoice.paid can arrive before checkout.session.completed
        sub = await _upsert_subscription(db, stripe.Subscription.retrieve(stripe_id))
    return sub


def _invoice_subscription_id(invoice: dict) -> str | None:
    sub_id = invoice.get("subscription")
    if not sub_id:
        parent = invoice.get("parent") or {}
        sub_id = (parent.get("subscription_details") or {}).get("subscription")
    if isinstance(sub_id, dict):
        sub_id = sub_id.get("id")
    return sub_id


async def handle_checkout_completed(session: dict, db: AsyncSession) -> None:
    sub_id = session.get("subscription")
    if not sub_id:
        return
    await _load_subscription(db, sub_id)


async def handle_invoice_paid(invoice: dict, db: AsyncSession) -> None:
    """Give the student this month's lesson credits (once per invoice)."""
    sub_id = _invoice_subscription_id(invoice)
    invoice_id = invoice.get("id")
    if not sub_id or not invoice_id:
        return

    already = await db.execute(
        select(CreditGrant.id).where(CreditGrant.stripe_invoice_id == invoice_id)
    )
    if already.first() is not None:
        return

    sub = await _load_subscription(db, sub_id)
    if sub is None:
        return
    plan = (
        await db.execute(select(PriceConfig).where(PriceConfig.product_key == sub.product_key))
    ).scalar_one_or_none()
    if plan is None or not plan.lessons_per_month:
        logger.error("Paid invoice for unknown plan %s", sub.product_key)
        return

    # Credits last until the end of the billing month this invoice paid for
    period_end = None
    lines = (invoice.get("lines") or {}).get("data") or []
    if lines:
        period_end = _ts((lines[0].get("period") or {}).get("end"))
    period_end = period_end or sub.current_period_end or _ts(invoice.get("period_end"))
    if period_end is None:
        logger.error("Cannot work out credit expiry for invoice %s", invoice_id)
        return

    sub.status = "active"
    if sub.current_period_end is None or period_end > sub.current_period_end:
        sub.current_period_end = period_end
    await credit_service.grant_credits(
        db,
        student_id=sub.student_id,
        total=plan.lessons_per_month,
        expires_at=period_end,
        source="subscription",
        subscription_id=sub.id,
        stripe_invoice_id=invoice_id,
    )


async def handle_subscription_changed(sub_obj: dict, db: AsyncSession) -> None:
    """customer.subscription.updated / deleted: keep our copy in sync."""
    await _upsert_subscription(db, sub_obj)
