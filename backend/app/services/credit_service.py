"""Lesson credits and the free trial.

Credits come in grants (one per paid plan month, or added by the tutor).
A plan lesson takes one credit from the grant that expires soonest, and only
grants that are still valid when the lesson starts can be used. A credit is
returned when the lesson is cancelled with enough notice.
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.credit_grant import CreditGrant

logger = logging.getLogger(__name__)


async def find_usable_grant(
    db: AsyncSession,
    student_id: uuid.UUID,
    lesson_start: datetime,
) -> CreditGrant | None:
    """Return the grant to take a credit from, locking it, or None.

    Picks the grant with credits left that expires soonest, among grants still
    valid at the lesson's start time.
    """
    result = await db.execute(
        select(CreditGrant)
        .where(
            and_(
                CreditGrant.student_id == student_id,
                CreditGrant.used < CreditGrant.total,
                CreditGrant.expires_at > lesson_start,
                CreditGrant.expires_at > datetime.now(tz=timezone.utc),
            )
        )
        .order_by(CreditGrant.expires_at.asc())
        .limit(1)
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def return_credit(db: AsyncSession, grant_id: uuid.UUID | None) -> bool:
    """Give a credit back to its grant. Returns True if one was returned."""
    if grant_id is None:
        return False
    result = await db.execute(
        select(CreditGrant).where(CreditGrant.id == grant_id).with_for_update()
    )
    grant = result.scalar_one_or_none()
    if grant is None or grant.used <= 0:
        return False
    grant.used -= 1
    await db.flush()
    return True


async def grant_credits(
    db: AsyncSession,
    student_id: uuid.UUID,
    total: int,
    expires_at: datetime,
    source: str,
    subscription_id: uuid.UUID | None = None,
    stripe_invoice_id: str | None = None,
    note: str | None = None,
) -> CreditGrant:
    grant = CreditGrant(
        student_id=student_id,
        subscription_id=subscription_id,
        source=source,
        total=total,
        used=0,
        expires_at=expires_at,
        stripe_invoice_id=stripe_invoice_id,
        note=note,
    )
    db.add(grant)
    await db.flush()
    logger.info(
        "Lesson credits granted",
        extra={"student_id": str(student_id), "total": total, "source": source},
    )
    return grant


async def credit_summary(db: AsyncSession, student_id: uuid.UUID) -> dict:
    """Credits the student can still use, and when the soonest ones expire."""
    now = datetime.now(tz=timezone.utc)
    result = await db.execute(
        select(
            func.coalesce(func.sum(CreditGrant.total - CreditGrant.used), 0),
            func.min(CreditGrant.expires_at),
        ).where(
            and_(
                CreditGrant.student_id == student_id,
                CreditGrant.expires_at > now,
                CreditGrant.used < CreditGrant.total,
            )
        )
    )
    remaining, soonest = result.one()
    return {"credits_remaining": int(remaining), "credits_expire_at": soonest}


async def trial_available(db: AsyncSession, student_id: uuid.UUID) -> bool:
    """A student gets one free trial.

    The trial is used once a trial booking is active or completed, or was
    cancelled with less than 12 hours' notice. A trial cancelled in time can
    be booked again.
    """
    result = await db.execute(
        select(Booking.id)
        .where(
            and_(
                Booking.student_id == student_id,
                Booking.booking_type == "trial",
                or_(
                    Booking.status.in_(["pending_payment", "confirmed", "completed"]),
                    Booking.late_cancellation.is_(True),
                ),
            )
        )
        .limit(1)
    )
    return result.first() is None
