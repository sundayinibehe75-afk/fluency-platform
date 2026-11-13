"""Admin router — students and lesson credits.

Endpoints (admin only):
- GET   /admin/stats                          — overview numbers for this month
- GET/PUT /admin/settings/exchange-rate       — naira per dollar for Paystack checkout
- GET   /admin/students                       — students with plan, credits, trial, goal
- GET   /admin/students/{id}/credits          — a student's credit grants
- POST  /admin/students/{id}/credits          — add lessons (e.g. a goodwill credit)
- PATCH /admin/credits/{grant_id}             — extend expiry and/or add lessons
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.models.user import User
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


class ExchangeRate(BaseModel):
    ngn_per_usd: Decimal = Field(gt=0, le=100000)


class AddCredits(BaseModel):
    lessons: int = Field(ge=1, le=100)
    expires_at: datetime
    note: Optional[str] = Field(default=None, max_length=500)


class UpdateGrant(BaseModel):
    expires_at: Optional[datetime] = None
    add_lessons: Optional[int] = Field(default=None, ge=-100, le=100)


@router.get("/settings/exchange-rate")
async def get_exchange_rate(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
) -> dict:
    from app.services import paystack_service

    rate = await paystack_service.get_rate(db)
    return {"ngn_per_usd": float(rate) if rate is not None else None}


@router.put("/settings/exchange-rate")
async def set_exchange_rate(
    body: ExchangeRate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
) -> dict:
    """Naira per US dollar, used to charge dollar prices in naira (Paystack)."""
    from app.services import paystack_service

    rate = await paystack_service.set_rate(db, body.ngn_per_usd)
    return {"ngn_per_usd": float(rate)}


@router.get("/stats")
async def stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> dict:
    return await admin_service.stats(db, current_user)


@router.get("/students")
async def list_students(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
) -> list[dict]:
    return await admin_service.list_students(db)


@router.get("/students/{student_id}/credits")
async def list_grants(
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
) -> list[dict]:
    return await admin_service.list_grants(db, student_id)


@router.post("/students/{student_id}/credits", status_code=201)
async def add_credits(
    student_id: uuid.UUID,
    body: AddCredits,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
) -> dict:
    return await admin_service.add_credits(db, student_id, body.lessons, body.expires_at, body.note)


@router.patch("/credits/{grant_id}")
async def update_grant(
    grant_id: uuid.UUID,
    body: UpdateGrant,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
) -> dict:
    return await admin_service.update_grant(db, grant_id, body.expires_at, body.add_lessons)
