"""Security utilities: password hashing, JWT creation/decoding, denylist check."""
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.jwt_denylist import JwtDenylist

# ---------------------------------------------------------------------------
# Password hashing — bcrypt with cost factor 12
# Uses the bcrypt library directly to avoid passlib compatibility issues
# with newer bcrypt versions.
# ---------------------------------------------------------------------------
_BCRYPT_ROUNDS = 12


def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt (cost factor 12)."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the bcrypt *hashed* value."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ---------------------------------------------------------------------------
# JWT — HS256, 24-hour expiry
# ---------------------------------------------------------------------------
_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_SECONDS = 86_400  # 24 hours


def create_access_token(user_id: str | uuid.UUID, email: str, role: str) -> str:
    """Create a signed HS256 JWT for the given user.

    Claims included:
    - ``sub``   — user_id (str)
    - ``email`` — user email
    - ``role``  — user role
    - ``jti``   — unique token ID (uuid4)
    - ``iat``   — issued-at (UTC epoch seconds)
    - ``exp``   — expiry (iat + 86400 s)
    """
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=_ACCESS_TOKEN_EXPIRE_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT.

    Returns the decoded payload dict on success.
    Raises ``HTTPException(401)`` if the token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "UNAUTHORIZED", "detail": "Invalid or expired token."},
            headers={"WWW-Authenticate": "Bearer"},
        )


async def is_token_denylisted(jti: str, db: AsyncSession) -> bool:
    """Return True if the given JTI is present in the ``jwt_denylist`` table."""
    result = await db.execute(
        select(JwtDenylist).where(JwtDenylist.jti == jti)
    )
    return result.scalar_one_or_none() is not None
