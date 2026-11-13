"""Admin tools: students overview and managing lesson credits."""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit_grant import CreditGrant
from app.models.user import User
from app.services import credit_service, subscription_service


async def list_students(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(User).where(User.role == "student").order_by(User.first_name, User.last_name)
    )
    students = []
    for user in result.scalars():
        info = await subscription_service.my_plan(db, user.id)
        students.append(
            {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "cefr_level": user.cefr_level,
                "timezone": user.timezone,
                "learning_goal": user.learning_goal,
                "goal_note": user.goal_note,
                "created_at": user.created_at,
                **info,
            }
        )
    return students


async def _get_student(db: AsyncSession, student_id: uuid.UUID) -> User:
    user = (await db.execute(select(User).where(User.id == student_id))).scalar_one_or_none()
    if user is None or user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Student not found."},
        )
    return user


def _grant_dict(g: CreditGrant) -> dict:
    return {
        "id": g.id,
        "source": g.source,
        "total": g.total,
        "used": g.used,
        "remaining": g.total - g.used,
        "lesson_minutes": g.lesson_minutes,
        "expires_at": g.expires_at,
        "note": g.note,
        "created_at": g.created_at,
    }


async def list_grants(db: AsyncSession, student_id: uuid.UUID) -> list[dict]:
    await _get_student(db, student_id)
    result = await db.execute(
        select(CreditGrant)
        .where(CreditGrant.student_id == student_id)
        .order_by(CreditGrant.expires_at.desc())
    )
    return [_grant_dict(g) for g in result.scalars()]


def _future(expires_at: datetime) -> datetime:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(tz=timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "detail": "The expiry date must be in the future."},
        )
    return expires_at


async def add_credits(
    db: AsyncSession,
    student_id: uuid.UUID,
    lessons: int,
    expires_at: datetime,
    note: str | None,
    lesson_minutes: int = 60,
) -> dict:
    await _get_student(db, student_id)
    grant = await credit_service.grant_credits(
        db,
        student_id=student_id,
        total=lessons,
        expires_at=_future(expires_at),
        source="admin",
        note=note,
        lesson_minutes=lesson_minutes,
    )
    return _grant_dict(grant)


async def update_grant(
    db: AsyncSession,
    grant_id: uuid.UUID,
    expires_at: datetime | None,
    add_lessons: int | None,
) -> dict:
    """Extend a grant's expiry and/or add lessons to it."""
    grant = (
        await db.execute(select(CreditGrant).where(CreditGrant.id == grant_id).with_for_update())
    ).scalar_one_or_none()
    if grant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Credits not found."},
        )
    if expires_at is not None:
        grant.expires_at = _future(expires_at)
    if add_lessons:
        if grant.total + add_lessons < grant.used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "VALIDATION_ERROR", "detail": "Cannot remove credits that are already used."},
            )
        grant.total += add_lessons
    await db.flush()
    return _grant_dict(grant)


async def remove_unused(db: AsyncSession, grant_id: uuid.UUID) -> dict:
    """Take back a grant's unused lessons (e.g. added by mistake).

    Lessons you added that were never used: the grant is deleted. Otherwise it
    keeps the used lessons (so past bookings stay correct) and loses the rest;
    paid grants stay on record so income figures don't change. No refund is
    made for paid lessons.
    """
    grant = (
        await db.execute(select(CreditGrant).where(CreditGrant.id == grant_id).with_for_update())
    ).scalar_one_or_none()
    if grant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "detail": "Credits not found."},
        )
    if grant.used == 0 and grant.source == "admin":
        await db.delete(grant)
        await db.flush()
        return {"deleted": True, "removed": grant.total}
    removed = grant.total - grant.used
    grant.total = grant.used
    await db.flush()
    return {"deleted": False, "removed": removed}


async def stats(db: AsyncSession, admin: User) -> dict:
    """Numbers for the admin overview. "This month" uses the admin's time zone."""
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    from sqlalchemy import and_, func

    from app.core.timefmt import is_valid_timezone
    from app.models.availability_slot import AvailabilitySlot
    from app.models.booking import Booking
    from app.models.payment import Payment
    from app.models.subscription import Subscription

    zone = ZoneInfo(admin.timezone if is_valid_timezone(admin.timezone) else "UTC")
    now = datetime.now(tz=timezone.utc)
    local_now = now.astimezone(zone)
    month_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)

    async def scalar(query):
        return (await db.execute(query)).scalar() or 0

    single_paid = await scalar(
        select(func.sum(Payment.amount_cents)).where(
            Payment.status == "succeeded", Payment.created_at >= month_start
        )
    )
    refunded = await scalar(
        select(func.sum(Payment.amount_cents)).where(
            Payment.status == "refunded", Payment.created_at >= month_start
        )
    )
    plan_paid = await scalar(
        select(func.sum(CreditGrant.amount_cents)).where(
            CreditGrant.source.in_(["subscription", "package"]), CreditGrant.created_at >= month_start
        )
    )

    lessons_month = select(func.count(Booking.id)).join(
        AvailabilitySlot, Booking.slot_id == AvailabilitySlot.id
    )
    taught = await scalar(
        lessons_month.where(
            and_(
                Booking.status.in_(["confirmed", "completed"]),
                AvailabilitySlot.start_at >= month_start,
                AvailabilitySlot.end_at <= now,
            )
        )
    )
    upcoming_week = await scalar(
        lessons_month.where(
            and_(
                Booking.status == "confirmed",
                AvailabilitySlot.start_at > now,
                AvailabilitySlot.start_at <= now + timedelta(days=7),
            )
        )
    )
    trials_month = await scalar(
        lessons_month.where(
            and_(
                Booking.booking_type == "trial",
                Booking.status.in_(["confirmed", "completed"]),
                AvailabilitySlot.start_at >= month_start,
            )
        )
    )
    late_cancellations = await scalar(
        lessons_month.where(
            and_(Booking.late_cancellation.is_(True), AvailabilitySlot.start_at >= month_start)
        )
    )

    plan_rows = (
        await db.execute(
            select(Subscription.product_key, func.count(Subscription.id))
            .where(Subscription.status.in_(["active", "trialing", "past_due"]))
            .group_by(Subscription.product_key)
        )
    ).all()
    plans_by_type = {key: count for key, count in plan_rows}

    students = await scalar(select(func.count(User.id)).where(User.role == "student"))
    new_students = await scalar(
        select(func.count(User.id)).where(User.role == "student", User.created_at >= month_start)
    )

    # Trial students who went on to buy a plan
    tried = select(Booking.student_id).where(
        Booking.booking_type == "trial", Booking.status.in_(["confirmed", "completed"])
    )
    trial_students = await scalar(select(func.count(func.distinct(Booking.student_id))).where(
        Booking.booking_type == "trial", Booking.status.in_(["confirmed", "completed"])
    ))
    converted = await scalar(
        select(func.count(func.distinct(Subscription.student_id))).where(Subscription.student_id.in_(tried))
    )

    return {
        "month_label": f"{local_now:%B %Y}",
        "income_this_month_cents": int(single_paid) + int(plan_paid) - int(refunded),
        "lessons_taught_this_month": taught,
        "upcoming_next_7_days": upcoming_week,
        "trials_this_month": trials_month,
        "late_cancellations_this_month": late_cancellations,
        "active_plans": sum(plans_by_type.values()),
        "plans_by_type": plans_by_type,
        "students": students,
        "new_students_this_month": new_students,
        "trial_students": trial_students,
        "trial_to_plan": converted,
    }
