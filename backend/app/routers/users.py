"""Users router — the signed-in user's own profile.

Endpoints:
- GET   /users/me — profile with level, learning goal and time zone
- PATCH /users/me — update any of those (send only the fields to change)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.users import ProfileResponse, ProfileUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=ProfileResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> ProfileResponse:
    return ProfileResponse.model_validate(current_user)


@router.patch("/me", response_model=ProfileResponse)
async def update_me(
    body: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProfileResponse:
    for field, value in body.model_dump(exclude_unset=True).items():
        if field in ("first_name", "last_name", "timezone") and value is None:
            continue  # these can't be cleared
        setattr(current_user, field, value)
    await db.flush()
    await db.refresh(current_user)
    return ProfileResponse.model_validate(current_user)
