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
    db: AsyncSession, student_id: uuid.UUID, lessons: int, expires_at: datetime, note: str | None
) -> dict:
    await _get_student(db, student_id)
    grant = await credit_service.grant_credits(
        db,
        student_id=student_id,
        total=lessons,
        expires_at=_future(expires_at),
        source="admin",
        note=note,
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
