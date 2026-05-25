"""Authentication business logic.

Functions:
- register_student   — create a new student account, return JWT
- login              — verify credentials, return JWT
- logout             — add JTI to denylist
- request_password_reset — generate reset token, send email
- confirm_password_reset — validate token, update password
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.jwt_denylist import JwtDenylist
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GENERIC_AUTH_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail={"error": "UNAUTHORIZED", "detail": "Invalid email or password."},
    headers={"WWW-Authenticate": "Bearer"},
)


def _hash_reset_token(raw_token: str) -> str:
    """SHA-256 hash of a raw reset token (stored in DB, never the raw value)."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def register_student(db: AsyncSession, data: RegisterRequest) -> TokenResponse:
    """Create a new student account.

    Raises HTTP 409 if the email is already registered.
    Returns a JWT on success.
    """
    # Check email uniqueness
    result = await db.execute(select(User).where(User.email == data.email))
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "EMAIL_IN_USE", "detail": "Email is already registered."},
        )

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        role="student",
        cefr_level=data.cefr_level,
    )
    db.add(user)
    await db.flush()  # populate user.id before creating token

    # Send welcome email (fire-and-forget)
    try:
        from app.services.notification_service import send_email
        from app.core.config import settings

        await send_email(
            to=user.email,
            template_name="welcome",
            context={
                "first_name": user.first_name,
                "frontend_url": settings.frontend_url,
            },
        )
    except Exception:
        logger.exception(
            "Failed to send welcome email",
            extra={"user_id": str(user.id)},
        )

    token = create_access_token(user.id, user.email, user.role)
    return TokenResponse(access_token=token)


async def login(db: AsyncSession, data: LoginRequest) -> TokenResponse:
    """Verify credentials and return a JWT.

    Uses a generic error for both "not found" and "wrong password" to avoid
    leaking whether an email exists (Requirements 1.6, 1.7).
    """
    result = await db.execute(select(User).where(User.email == data.email))
    user: User | None = result.scalar_one_or_none()

    if user is None or not verify_password(data.password, user.password_hash):
        raise _GENERIC_AUTH_ERROR

    token = create_access_token(user.id, user.email, user.role)
    return TokenResponse(access_token=token)


async def logout(db: AsyncSession, token_data: dict) -> None:
    """Insert the token's JTI into the denylist so it cannot be reused.

    *token_data* is the decoded JWT payload dict (must contain ``jti`` and
    ``exp`` claims).
    """
    jti: str = token_data["jti"]
    exp_ts: int = token_data["exp"]
    expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc)

    entry = JwtDenylist(jti=jti, expires_at=expires_at)
    db.add(entry)
    # Commit is handled by get_db dependency


async def request_password_reset(
    db: AsyncSession,
    email: str,
    notification_service=None,
) -> None:
    """Generate a secure reset token, store its hash, and send a reset email.

    If the email is not found we silently succeed to avoid user enumeration.
    The email is sent fire-and-forget (errors are logged, not raised).
    """
    result = await db.execute(select(User).where(User.email == email))
    user: User | None = result.scalar_one_or_none()

    if user is None:
        # Silently succeed — do not reveal whether the email exists
        return

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_reset_token(raw_token)
    expires_at = datetime.now(tz=timezone.utc) + timedelta(hours=1)

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        used=False,
    )
    db.add(reset_token)
    await db.flush()

    # Fire-and-forget email notification
    if notification_service is not None:
        try:
            await notification_service.send_email(
                to=user.email,
                template_name="password_reset",
                context={
                    "first_name": user.first_name,
                    "reset_token": raw_token,
                    "expires_minutes": 60,
                },
            )
        except Exception:
            logger.exception(
                "Failed to send password reset email",
                extra={"user_id": str(user.id)},
            )


async def confirm_password_reset(
    db: AsyncSession,
    token: str,
    new_password: str,
) -> None:
    """Validate the reset token and update the user's password.

    Raises HTTP 400 if the token is invalid, expired, or already used.
    """
    token_hash = _hash_reset_token(token)
    now = datetime.now(tz=timezone.utc)

    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    reset_token: PasswordResetToken | None = result.scalar_one_or_none()

    _invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"error": "INVALID_TOKEN", "detail": "Token is invalid or has expired."},
    )

    if reset_token is None:
        raise _invalid
    if reset_token.used:
        raise _invalid
    if reset_token.expires_at < now:
        raise _invalid

    # Fetch the user and update password
    user_result = await db.execute(select(User).where(User.id == reset_token.user_id))
    user: User | None = user_result.scalar_one_or_none()
    if user is None:
        raise _invalid

    user.password_hash = hash_password(new_password)
    reset_token.used = True
    # Commit is handled by get_db dependency
