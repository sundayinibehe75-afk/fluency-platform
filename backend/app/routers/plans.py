"""Plans router — prices, monthly plans and the student's credits.

Endpoints:
- GET  /plans                      — public, active prices (single lesson + plans)
- GET  /subscriptions/me           — student, plan status, credits, free trial
- POST /subscriptions/checkout     — student, start Stripe Checkout for a plan
- POST /subscriptions/me/cancel    — student, stop renewal (keeps current month)
- POST /subscriptions/me/resume    — student, undo the cancellation
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.models.user import User
from app.services import subscription_service

router = APIRouter(tags=["plans"])


class PlanCheckoutRequest(BaseModel):
    product_key: str
    auto_renew: bool = False


@router.get("/plans")
async def list_plans(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await subscription_service.list_prices(db)


@router.get("/subscriptions/me")
async def my_plan(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student")),
) -> dict:
    return await subscription_service.my_plan(db, current_user.id)


@router.post("/subscriptions/checkout")
async def plan_checkout(
    body: PlanCheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student")),
) -> dict:
    return await subscription_service.create_checkout(db, current_user, body.product_key, body.auto_renew)


@router.post("/subscriptions/me/cancel")
async def cancel_plan(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student")),
) -> dict:
    return await subscription_service.cancel_subscription(db, current_user)


@router.post("/subscriptions/me/resume")
async def resume_plan(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student")),
) -> dict:
    return await subscription_service.resume_subscription(db, current_user)
