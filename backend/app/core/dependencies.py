"""FastAPI dependency functions.

- get_db: yields an AsyncSession for the request lifetime
- get_current_user: decode Bearer token, check denylist, return User
- require_role: factory that raises 403 if user's role is not allowed
"""
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token, is_token_denylisted
from app.db.session import AsyncSessionLocal
from app.models.user import User

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession and close it when the request is done."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode the Bearer JWT, check the denylist, and return the User.

    Raises HTTP 401 on any failure (missing token, invalid/expired token,
    denylisted token, or user not found in DB).
    """
    _unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "UNAUTHORIZED", "detail": "Not authenticated."},
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise _unauthorized

    token = credentials.credentials

    # Decode — raises 401 internally on failure
    payload = decode_access_token(token)

    jti: str | None = payload.get("jti")
    user_id: str | None = payload.get("sub")

    if not jti or not user_id:
        raise _unauthorized

    # Check denylist
    if await is_token_denylisted(jti, db):
        raise _unauthorized

    # Fetch user from DB
    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()

    if user is None:
        raise _unauthorized

    return user


def require_role(*roles: str):
    """Dependency factory that enforces role-based access control.

    Usage::

        @router.get("/admin-only")
        async def admin_endpoint(user = Depends(require_role("admin"))):
            ...

    Raises HTTP 403 if the authenticated user's role is not in *roles*.
    """

    async def _check_role(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "detail": "Insufficient permissions."},
            )
        return current_user

    return _check_role
